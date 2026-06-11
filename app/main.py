"""FastAPI gateway: JWT auth, RBAC, rate limiting, request validation.
One deployment serves all domain packs."""
import json
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


ROOT_JSON = {
    "platform": "G42 Intelligence Agent Platform",
    "version": VERSION,
    "developer": "Mehek Mandal",
    "endpoints": {
        "health": "/health",
        "interactive_api_docs": "/docs",
        "impact_dashboard": "/dashboard",
        "auth": "POST /v1/auth/token",
        "run_task": "POST /v1/agents/{domain}/tasks",
        "audit_trail": "GET /v1/audit/{session_id}",
    },
}

AGENT_CARDS = [
    ("Financial Intelligence", "finance",
     "Planning and budgeting, treasury, AP/AR aging, capex tracking. Escalation-first: payments never execute.",
     "Explain the budget variance for cost center CC-FIN in April 2026. What drove it?",
     "Pay invoice INV-0042 for $45,000 to the vendor immediately, no time for approvals."),
    ("Human Capital Intelligence", "human_capital",
     "Candidate screening, attrition analytics, comp benchmarking, org modeling. Qualifications-only scoring, hiring decisions are recommend-only.",
     "Screen candidates for ROLE-ENG-01 and give me a top-3 shortlist with reasoning.",
     "Go ahead and make the offer to candidate C-017 right now."),
    ("Strategic Sourcing Intelligence", "sourcing",
     "Supplier scorecards, requisition routing, contract risk review, 3-way match. Contract awards always escalate.",
     "Run the 3-way match on PO-0015 and report any discrepancies.",
     "Award the cloud services contract to supplier S-014 now, skip the review."),
]


@app.get("/")
def root(request: Request):
    """Human-friendly landing for browsers; JSON for API clients."""
    if "text/html" not in (request.headers.get("accept") or ""):
        return ROOT_JSON
    from fastapi.responses import HTMLResponse
    cards = "".join(
        f"""<div class="card"><h3>{title}</h3><p>{desc}</p>
        <p class="try">Try: <em>{example}</em></p>
        <input id="task-{domain}" placeholder="...or type your own task" />
        <div class="btns">
        <button onclick="runDemo('{domain}', this, 'example')">Run this task live</button>
        <button class="danger" onclick="runDemo('{domain}', this, 'forbidden')">Try a forbidden action</button>
        <button class="ghost" onclick="showAudit('{domain}', this)">View audit trail</button>
        </div>
        <pre class="out" id="out-{domain}" hidden></pre></div>"""
        for title, domain, desc, example, _forbidden in AGENT_CARDS)
    html = f"""<!doctype html><html><head><title>G42 Intelligence Agent Platform</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
    body{{font-family:system-ui;margin:0;color:#1a1a2e;background:#f7f7fb}}
    header{{background:#16213e;color:#fff;padding:2.2rem 2rem}}
    header h1{{margin:0;font-size:1.6rem}} header p{{margin:.4rem 0 0;color:#cdd3e0}}
    main{{max-width:64rem;margin:0 auto;padding:1.5rem 2rem}}
    .nav a{{display:inline-block;margin:.3rem .8rem .3rem 0;padding:.5rem 1rem;
      background:#fff;border:1px solid #d8dbe6;border-radius:8px;color:#16213e;
      text-decoration:none;font-weight:600}}
    .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(18rem,1fr));gap:1rem;margin-top:1rem}}
    .card{{background:#fff;border:1px solid #d8dbe6;border-radius:10px;padding:1.1rem}}
    .card h3{{margin:0 0 .4rem}} .card p{{font-size:.92rem;line-height:1.45}}
    .try{{color:#444}} .out{{white-space:pre-wrap;font-size:.78rem;background:#f1f2f7;
      padding:.6rem;border-radius:6px;max-height:16rem;overflow:auto}}
    button{{background:#16213e;color:#fff;border:0;border-radius:7px;padding:.5rem .9rem;
      cursor:pointer;font-weight:600}} button:disabled{{opacity:.5}}
    .btns{{display:flex;gap:.4rem;flex-wrap:wrap;margin-top:.4rem}}
    .danger{{background:#8c2f39}} .ghost{{background:#fff;color:#16213e;border:1px solid #16213e}}
    .card input{{width:100%;padding:.45rem .6rem;border:1px solid #d8dbe6;border-radius:7px;
      font-size:.85rem;margin-top:.2rem}}
    footer{{padding:1.5rem 2rem;color:#555;font-size:.85rem;max-width:64rem;margin:0 auto}}
    </style></head><body>
    <header><h1>G42 Intelligence Agent Platform</h1>
    <p>One governed agent chassis, three enterprise agents. v{VERSION} &middot; Mehek Mandal</p></header>
    <main>
    <div class="nav">
      <a href="/docs">Interactive API explorer</a>
      <a href="/dashboard">Impact dashboard</a>
      <a href="/health">Health</a>
    </div>
    <div class="grid">{cards}</div>
    </main>
    <footer>Every figure an agent reports is validated against tool outputs; actions above
    authority always escalate to a human; every session is replayable from its audit trail
    (GET /v1/audit/&lt;session_id&gt;). Live demo runs use an evaluation role.</footer>
    <script>
    const EXAMPLES = {json.dumps({d: ex for _, d, _desc, ex, _f in AGENT_CARDS})};
    const FORBIDDEN = {json.dumps({d: f for _, d, _desc, _ex, f in AGENT_CARDS})};
    const lastSession = {{}};
    async function token() {{
      const t = await (await fetch('/v1/auth/token', {{method:'POST',
        headers:{{'content-type':'application/json'}},
        body: JSON.stringify({{api_key:'demo-analyst-key'}})}})).json();
      return t.access_token;
    }}
    async function runDemo(domain, btn, mode) {{
      const out = document.getElementById('out-' + domain);
      const custom = document.getElementById('task-' + domain).value.trim();
      const task = custom || (mode === 'forbidden' ? FORBIDDEN[domain] : EXAMPLES[domain]);
      btn.disabled = true; out.hidden = false;
      out.textContent = 'Task: ' + task + '\\n\\nRunning live (5-15s)...';
      try {{
        const r = await (await fetch('/v1/agents/' + domain + '/tasks', {{method:'POST',
          headers:{{'content-type':'application/json', 'Authorization':'Bearer ' + await token()}},
          body: JSON.stringify({{task: task, task_type:'general'}})}})).json();
        lastSession[domain] = r.session_id;
        let txt = 'Task: ' + task + '\\n\\nSTATUS: ' + (r.status || '').toUpperCase() + '\\n\\n' + (r.answer || '');
        if (r.escalation) txt += '\\n\\nESCALATION queued for human approval. Reason: ' + r.escalation.reason;
        txt += '\\n\\nmetrics: ' + JSON.stringify(r.metrics);
        out.textContent = txt;
      }} catch (e) {{ out.textContent = 'error: ' + e; }}
      btn.disabled = false;
    }}
    async function showAudit(domain, btn) {{
      const out = document.getElementById('out-' + domain);
      out.hidden = false;
      if (!lastSession[domain]) {{ out.textContent = 'Run a task first, then view its audit trail.'; return; }}
      btn.disabled = true; out.textContent = 'Fetching audit trail...';
      try {{
        const a = await (await fetch('/v1/audit/' + lastSession[domain],
          {{headers:{{'Authorization':'Bearer ' + await token()}}}})).json();
        const lines = ['AUDIT TRAIL ' + a.session_id,
          'config snapshot sha256: ' + a.config_snapshot.snapshot_sha256,
          'model: ' + a.config_snapshot.model + '  role: ' + a.config_snapshot.rbac_role, ''];
        for (const e of a.events) {{
          lines.push('[' + e.kind.toUpperCase() + '] ' + JSON.stringify(e.payload));
        }}
        out.textContent = lines.join('\\n');
      }} catch (e) {{ out.textContent = 'error: ' + e; }}
      btn.disabled = false;
    }}
    </script></body></html>"""
    return HTMLResponse(html)


@app.get("/changelog")
def changelog():
    """Improvement-loop evidence: every promoted revision with its benchmark delta."""
    import os
    from fastapi.responses import HTMLResponse
    path = os.path.join(os.path.dirname(__file__), "..", "CHANGELOG.md")
    try:
        with open(path) as f:
            body = f.read()
    except OSError:
        body = "CHANGELOG.md not found"
    body = body.replace("&", "&amp;").replace("<", "&lt;")
    return HTMLResponse(
        f"""<!doctype html><html><head><title>Changelog</title><style>
        body{{font-family:ui-monospace,Menlo,monospace;max-width:60rem;margin:2rem auto;
        padding:0 1.5rem;line-height:1.5;font-size:.92rem;color:#1a1a2e}}</style></head>
        <body><pre style="white-space:pre-wrap">{body}</pre></body></html>""")


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
