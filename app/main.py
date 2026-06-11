"""FastAPI gateway: JWT auth, RBAC, rate limiting, request validation.
One deployment serves all domain packs."""
import time
from collections import defaultdict, deque

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from . import audit
from .agent import AgentRunner
from .auth import current_principal, mint_token
from .config import VERSION
from .llm import LLMClient
from .packs.base import list_packs, load_pack
from .telemetry import init_tracing

app = FastAPI(title="G42 Intelligence Agent Platform", version=VERSION)

_started = time.time()
_runners: dict[tuple[str, str], AgentRunner] = {}
_rate: dict[str, deque] = defaultdict(deque)
RATE_LIMIT, RATE_WINDOW = 30, 60  # requests per principal per minute


@app.on_event("startup")
def _startup():
    audit.init_db()
    init_tracing()


def _check_rate(sub: str):
    q = _rate[sub]
    now = time.time()
    while q and now - q[0] > RATE_WINDOW:
        q.popleft()
    if len(q) >= RATE_LIMIT:
        raise HTTPException(429, "rate limit exceeded", headers={"Retry-After": "30"})
    q.append(now)


def _runner(domain: str, role: str) -> AgentRunner:
    if domain not in list_packs():
        raise HTTPException(404, f"unknown agent domain '{domain}'; available: {list_packs()}")
    key = (domain, role)
    if key not in _runners:
        _runners[key] = AgentRunner(load_pack(domain), role, LLMClient())
    return _runners[key]


class TokenRequest(BaseModel):
    api_key: str = Field(min_length=8, max_length=128)


class TaskRequest(BaseModel):
    task: str = Field(min_length=1, max_length=8000)
    task_type: str = Field(default="general", max_length=64)


@app.get("/health")
def health():
    return {"status": "ok", "version": VERSION, "uptime_seconds": round(time.time() - _started),
            "agents": list_packs()}


@app.post("/v1/auth/token")
def token(req: TokenRequest):
    return {"access_token": mint_token(req.api_key), "token_type": "bearer"}


@app.get("/v1/agents")
def agents(principal: dict = Depends(current_principal)):
    return {"agents": list_packs(), "role": principal["role"]}


@app.post("/v1/agents/{domain}/tasks")
def run_task(domain: str, req: TaskRequest, principal: dict = Depends(current_principal)):
    _check_rate(principal["sub"])
    runner = _runner(domain, principal["role"])
    return runner.run_task(req.task, req.task_type)


@app.get("/v1/audit/{session_id}")
def audit_trail(session_id: str, principal: dict = Depends(current_principal)):
    if principal["role"] not in ("admin", "analyst"):
        raise HTTPException(403, "audit access requires analyst or admin role")
    trail = audit.session_trail(session_id)
    if trail["config_snapshot"] is None:
        raise HTTPException(404, "unknown session")
    return trail


@app.get("/v1/impact")
def impact(principal: dict = Depends(current_principal)):
    return audit.impact_rollup()
