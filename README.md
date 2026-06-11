# G42 Intelligence Agent Platform

One production-grade agent chassis, three enterprise domain agents:

- **Financial Intelligence Agent** (req 732965122): planning and budgeting, treasury, AP/AR, capex, financial operations
- **Human Capital Intelligence Agent** (req 732965022): talent acquisition, HR operations, performance analytics, comp and org design
- **Strategic Sourcing Intelligence Agent** (req 732965422): supplier evaluation, requisition intake, sourcing decisions, contract review, 3-way match

Each agent is a domain pack (system prompt, tool set, dataset, eval suite) on
a shared chassis. One deployment serves all three.

## Architecture

```
FastAPI gateway (JWT auth, RBAC, rate limiting, request validation)
  -> Governance wrapper (config snapshots, Presidio PII redaction in/out,
     OTel traces, per-role tool allowlists, token/cost budget rails)
    -> LangGraph agent core (SQLite checkpointer = replayable audit trail,
       validator node with bounded self-correction, escalation gates)
      -> Domain packs (finance / human_capital / sourcing)
        -> Connector layer (synthetic datasets behind the same interface
           live ERP/HRIS/P2P connectors implement)
```

Model layer is one OpenAI-compatible client: `LLM_BASE_URL` + `LLM_MODEL`
swap between Anthropic, OpenAI, and G42 Compass/JAIS with zero code change.

## Run

```bash
cp .env.example .env   # set LLM_API_KEY
docker compose up -d
curl -s localhost:8000/health
```

Or locally: `pip install -r requirements.txt` (plus the spaCy model in the
Dockerfile), then `uvicorn app.main:app`.

```bash
# get a token, run a task
TOKEN=$(curl -s localhost:8000/v1/auth/token -d '{"api_key":"demo-analyst-key"}' -H 'content-type: application/json' | jq -r .access_token)
curl -s localhost:8000/v1/agents/finance/tasks -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{"task":"Explain the CC-FIN variance for 2026-04","task_type":"variance_analysis"}'
```

## Evaluate (reproducible)

```bash
python -m evals.harness finance 3     # 15 golden scenarios x 3 runs, judged vs oracles
python -m evals.bias human_capital    # identity-pair parity testing
python -m evals.redaction_test        # seeded-PII redaction efficacy
python -m stress.adversarial          # 10 attack classes vs live deployment
python -m stress.load_test            # gateway + end-to-end load profiles
```

Results land in `evals/results/` and `stress/results/` as JSON. The same
harness that produced the submitted benchmark numbers ships in this repo, so
any re-benchmark reproduces them.

## Key endpoints

| Endpoint | Purpose |
|---|---|
| `POST /v1/auth/token` | exchange scoped API key for JWT (role claim) |
| `POST /v1/agents/{domain}/tasks` | run a task on an agent |
| `GET /v1/audit/{session_id}` | full replayable session trail |
| `GET /v1/impact`, `GET /dashboard` | enterprise impact telemetry rollup |
| `GET /health` | liveness, version, registered agents |

## Docs

- [docs/deployment-runbook.md](docs/deployment-runbook.md): deploy, connect (Compass swap, live connectors), monitor, rollback
- [docs/impact-assumptions.md](docs/impact-assumptions.md): human-equivalent time assumptions behind the impact rollup
- [CHANGELOG.md](CHANGELOG.md): versioned config revisions with the benchmark deltas that justified them
