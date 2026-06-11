# Probationary Deployment Runbook

How the platform runs inside G42's environment. One chassis serves all three
agents; this runbook is shared.

## 1. Deploy

Single Docker image, configuration entirely by environment variable. No
external dependencies beyond the LLM endpoint; state is two SQLite files on
one volume (audit store + checkpoints).

```bash
docker compose up -d        # evaluation
```

| Env var | Purpose | Default |
|---|---|---|
| LLM_BASE_URL | OpenAI-compatible endpoint (Compass works here) | api.openai.com/v1 |
| LLM_MODEL | model name (jais-30b, gpt-oss-120b, gpt-4o-mini...) | gpt-4o-mini |
| LLM_API_KEY | endpoint credential | - |
| JWT_SECRET | token signing secret | change in production |
| ADMIN/ANALYST/VIEWER_API_KEY | scoped API keys per role | demo values |
| OTEL_EXPORTER_OTLP_ENDPOINT | trace export target | off |
| MAX_USD_PER_TASK / MAX_TOKENS_PER_TASK / MAX_LLM_CALLS_PER_TASK | budget rails | 0.50 / 60k / 16 |

**Azure path:** the image is cloud-agnostic; deploy to Azure Container Apps
(`az containerapp up --image <registry>/g42-agent-platform --target-port 8000`)
or AKS with the same env vars. The chassis is stateless except the data
volume; horizontal scale = N replicas sharing an Azure Files volume, or point
AUDIT_DB_PATH/CHECKPOINT_DB_PATH at a mounted database when scale demands.

## 2. Connect to G42 infrastructure

**Sovereign model swap (Compass/JAIS):** the model layer is one
OpenAI-compatible client. Pointing it at Compass is configuration, not code:

```bash
LLM_BASE_URL=https://api.core42.ai/v1   # Compass endpoint
LLM_MODEL=jais-30b-chat                  # or gpt-oss-120b, llama-3, azure gpt-4
LLM_API_KEY=<compass key>
```

**Real connectors:** each domain pack's tools currently read validated
synthetic datasets through one interface (fetch/normalize/cache, the Nucleus
pattern). Wiring a live system replaces the dataset read with the system
call; tool signatures, the agent graph, governance, and benchmarks are
unchanged. Interface contract per connector:

| Agent | Replace synthetic source with | Interface |
|---|---|---|
| Finance | ERP GL (SAP/Oracle/Dynamics), AP/AR subledger, treasury | `query_ledger`, `aging_report`, `cash_position` data providers |
| Human Capital | HRIS (Workday/SAP SF), ATS, comp system | `employees`, `candidates`, `comp_bands` providers |
| Sourcing | P2P (Ariba/Coupa), CLM, supplier master | `suppliers`, `purchase_orders`, `contracts` providers |
| All | M365/SharePoint/Monday.com (InceptionClaw stack) | document ingestion path, same redaction + injection defense |

## 3. Monitor

- `GET /health`: liveness, version, registered agents (Docker HEALTHCHECK uses it)
- OTel traces: every LLM call and tool call as spans (latency, tokens,
  redaction events) exported to any OTLP collector G42 already runs
- `GET /v1/audit/{session_id}`: full replayable trail per session
- `GET /v1/impact` and `/dashboard`: enterprise impact rollup

## 4. Rollback

Every promoted configuration is a hash-addressed snapshot recorded at session
start, with a CHANGELOG entry and the benchmark delta that justified it.
Rollback = repointing to the prior config snapshot; no redeploy. The human
approval gate in the improvement loop is also the rollback decision point.

## 5. Support during probation

Any incident is reconstructable: config snapshot (what was running), SQLite
checkpoints (every state transition, replayable), audit events (every
LLM/tool/redaction/escalation step). Issue triage = pull the session trail by
ID. Config fixes (prompt, threshold, tool description) ship without
redeployment and re-run the golden suite before promotion; the shipped eval
harness lets G42 re-benchmark any revision independently.
