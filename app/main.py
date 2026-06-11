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


@app.get("/")
def root():
    return {
        "platform": "G42 Intelligence Agent Platform",
        "version": VERSION,
        "developer": "Mehek Mandal",
        "agents": list_packs(),
        "endpoints": {
            "health": "/health",
            "interactive_api_docs": "/docs",
            "impact_dashboard": "/dashboard",
            "auth": "POST /v1/auth/token",
            "run_task": "POST /v1/agents/{domain}/tasks",
            "audit_trail": "GET /v1/audit/{session_id}",
        },
        "note": "Evaluation credentials are provided in the submission package.",
    }


@app.get("/health")
def health():
    return {"status": "ok", "version": VERSION, "uptime_seconds": round(time.time() - _started),
            "agents": list_packs()}


@app.post("/v1/auth/token")
def token(req: TokenRequest):
    return {"access_token": mint_token(req.api_key), "token_type": "bearer"}


@app.get("/v1/agents")
def agents(principal: dict = Depends(current_principal)):
    _check_rate(principal["sub"])
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


@app.get("/dashboard")
def dashboard():
    """Impact telemetry dashboard: the numbers value-linked compensation is
    computed from. Public-read by design for the demo; production deployments
    put it behind the same JWT gate."""
    from fastapi.responses import HTMLResponse
    r = audit.impact_rollup()
    rows = "".join(
        f"<tr><td>{d}</td><td>{m['tasks']}</td><td>{m['completed']}</td>"
        f"<td>{m['escalated']}</td><td>{m['escalation_rate']:.1%}</td>"
        f"<td>{m['human_equivalent_hours']:.1f}</td><td>{m['hours_saved']:.1f}</td>"
        f"<td>${m['cost_per_task_usd']:.4f}</td></tr>"
        for d, m in sorted(r["domains"].items()))
    html = f"""<!doctype html><html><head><title>Enterprise Impact</title><style>
    body{{font-family:system-ui;margin:2rem;color:#1a1a2e}}
    table{{border-collapse:collapse;width:100%;max-width:60rem}}
    th,td{{border:1px solid #ddd;padding:.5rem .8rem;text-align:left}}
    th{{background:#16213e;color:#fff}}h1{{font-size:1.4rem}}
    .big{{font-size:2rem;font-weight:700}}</style></head><body>
    <h1>G42 Intelligence Agent Platform: Enterprise Impact</h1>
    <p>Tasks automated: <span class="big">{r['totals']['tasks']}</span>
    &nbsp; Hours saved: <span class="big">{r['totals']['hours_saved']:.0f}</span>
    &nbsp; Total LLM cost: <span class="big">${r['totals']['cost_usd']:.2f}</span></p>
    <table><tr><th>Agent</th><th>Tasks</th><th>Completed</th><th>Escalated</th>
    <th>Escalation rate</th><th>Human-equivalent hours</th><th>Hours saved</th>
    <th>Cost per task</th></tr>{rows}</table>
    <p>Human-equivalent assumptions per task type are documented in
    docs/impact-assumptions.md. All figures derive from audit-grade telemetry.</p>
    </body></html>"""
    return HTMLResponse(html)
