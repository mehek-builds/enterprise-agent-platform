# Enterprise Agent Platform

**The G42 Intelligence Agent Platform: one production-grade, governed agent chassis running three enterprise domain agents.** Financial Intelligence (req 732965122), Human Capital Intelligence (req 732965022), and Strategic Sourcing Intelligence (req 732965422) are not three codebases. They are three *domain packs* (a system prompt, a tool set, a dataset, and an eval suite) mounted on a single shared chassis, and one deployment serves all three.

This is not a chatbot wrapper. It is a full enterprise-agent stack: a FastAPI gateway with JWT auth, RBAC, request validation and rate limiting; a LangGraph agent core whose every state transition is persisted by a SQLite checkpointer (so any session is replayable); a governance wrapper that snapshots the exact config each session ran under, redacts PII in and out with Microsoft Presidio, enforces per-role tool allowlists at the graph layer, and holds hard token/cost/call budget rails; a runtime validator that refuses to let the agent report a figure it cannot trace to a tool output; an escalation model where consequential actions (paying, hiring, awarding) are recommend-only and always route to a human; an OpenTelemetry trace layer; an impact-telemetry rollup that measures hours saved against documented human-equivalent assumptions; and a reproducible evaluation and adversarial-stress harness that ships in-repo, so the benchmark numbers reproduce. It is wired together over FastAPI, LangGraph, an OpenAI-compatible model client, SQLite, and Docker, and it deploys unchanged to Render, Azure Container Apps, AKS, or any VPS.

---

## The problem this solves

Every enterprise function now wants its own AI agent. Finance wants variance analysis and treasury support. HR wants candidate screening and attrition analytics. Procurement wants supplier scorecards and three-way match. So teams stand up an agent per function, and each one re-implements the same plumbing from scratch: authentication, role-based access control, tool calling, an audit trail, PII handling, cost controls, an evaluation harness. The domain logic is maybe twenty percent of the work. The other eighty percent is governance, and it gets rebuilt, badly, every time.

Rebuilding that plumbing per agent is not just wasteful, it is dangerous, for reasons that have nothing to do with the domain and everything to do with engineering:

1. **Ungoverned tool use.** An agent that can call a `pay_invoice` or `award_contract` tool is one hallucinated tool call away from moving money it should never have moved. The hard part is not exposing the tool, it is guaranteeing that consequential actions can never execute autonomously, regardless of how the user phrases the request or what a document embedded in the task tries to instruct.

2. **Ungrounded figures.** A finance agent that says "the variance was $77,329" and is wrong by an order of magnitude is worse than useless, it is a liability. The number has to be provably sourced from a tool result, not recalled, estimated, or invented. Very few agent stacks enforce this at runtime.

3. **No audit trail.** When an agent makes a decision, an enterprise needs to answer, months later, *exactly* what configuration, model, prompt, and data produced it. Most agent logs are a flat text stream that cannot be replayed or attributed.

4. **Fairness and PII exposure.** An HR screening agent that lets a candidate's name or nationality leak into a score is a discrimination lawsuit. An agent that echoes a personal phone number or IBAN into a log is a data-protection breach. Both need to be structurally impossible, not merely discouraged in a prompt.

5. **Unproven claims.** "Our agent is accurate and safe" means nothing without a reproducible benchmark: scenarios with oracle answers, an unbiased judge, adversarial attack coverage, and bias parity tests, all runnable by the reader.

6. **Vendor lock-in.** A sovereign-AI customer such as G42 cannot be bolted to one US model API. The model layer has to swap to G42's own Compass / JAIS endpoints with zero code change, or the platform is a non-starter.

**This platform solves all six as one shared chassis** and then proves each domain agent on top of it, rather than shipping three demos that each solve the domain and ignore the governance.

## Why you should care (even if you never touch enterprise software)

If you are reading this to understand what I can build: this repository takes the phrase "production-grade AI agent" and makes it literal. It is not a notebook and not a single prompt. It is a governed runtime with an auth model, an RBAC model enforced below the API at the graph layer, a self-correcting execution graph, a replayable audit store, a PII firewall, cost rails, an OpenTelemetry surface, a portable model layer, and a benchmark harness that reproduces its own reported numbers. The genuinely interesting engineering is the *separation*: a domain-agnostic chassis that knows nothing about finance or HR, and thin domain packs that carry all the domain knowledge, so a fourth agent is a new folder, not a new service. Everything is deterministic where it can be (the tools compute real answers from seeded data, no LLM guessing) and governed where it cannot be, and the whole thing runs on a schedule, defends itself against a suite of attacks, and shows its work.

---

## System architecture

A request enters at the top through the governed gateway and descends through the governance wrapper into the LangGraph core, which drives the act / validate loop against the mounted domain pack. Audit, redaction, and telemetry are cross-cutting: every layer writes to them.

```
                     POST /v1/agents/{domain}/tasks     (JWT bearer, role claim)
                                     |
        +----------------------------v----------------------------+
        |  FastAPI gateway            app/main.py                  |
        |  JWT auth  .  RBAC role  .  Pydantic validation  .       |
        |  per-principal rate limit (30 / 60s)                     |
        +----------------------------v----------------------------+
        |  Governance wrapper                                      |
        |  config snapshot (sha256, app/config.py)                |
        |  Presidio PII redaction IN   (app/redaction.py)         |
        |  per-role tool allowlist     (graph-level, app/agent.py)|
        |  token / cost / call budget rails (app/config.py)       |
        +----------------------------v----------------------------+
        |  LangGraph agent core        app/agent.py               |
        |                                                          |
        |     agent --(tool calls?)--> tools --> agent   (act)    |
        |     agent --(final answer)-> validate                   |
        |     validate --pass--> END                              |
        |     validate --fail--> agent  (critique fed back)       |
        |     escalate() tool call ---> END  status=escalated     |
        |     budget breach --------->  END  status=budget_exceeded|
        |                                                          |
        |  SQLite checkpointer = replayable state per transition  |
        +----------------------------v----------------------------+
        |  Domain pack   app/packs/{finance|human_capital|sourcing}|
        |  system_prompt.md . tools.py (TOOLS) . dataset/ . evals |
        +----------------------------v----------------------------+
        |  Connector layer: deterministic tools over seeded JSON  |
        |  (the same interface a live ERP / HRIS / P2P implements) |
        +---------------------------------------------------------+

   Cross-cutting, written by every layer:
   Audit store (app/audit.py, SQLite)     config_snapshots . audit_events . impact_telemetry
   PII redaction OUT (app/redaction.py)   applied to the final answer before return
   OpenTelemetry spans (app/telemetry.py) exported to any OTLP endpoint

   Model layer (app/llm.py): one OpenAI-compatible client.
   LLM_BASE_URL + LLM_MODEL swap between OpenAI, Anthropic, and G42 Compass / JAIS
   with zero code change.
```

The chassis is domain-agnostic: `app/` contains no finance, HR, or sourcing logic whatsoever. Everything domain-specific lives under `app/packs/<domain>/`, discovered at runtime by `list_packs()` scanning for any directory that carries a `system_prompt.md`. Adding a fourth enterprise agent is adding a fourth folder; no chassis change, no new deployment.

---

## The full stack

| Layer | Technologies |
|-------|--------------|
| **API / gateway** | FastAPI 0.136, Uvicorn 0.49, Pydantic request models with length bounds, per-principal in-memory sliding-window rate limiting (30 requests / 60s), an HTML landing + live demo page and a JSON API off the same routes |
| **Auth / RBAC** | PyJWT 2.13 (HS256), scoped API key exchanged for a short-TTL JWT carrying a role claim; three roles (admin, analyst, viewer); allowlists enforced at the graph layer, not only the gateway |
| **Agent core** | LangGraph 1.2 `StateGraph` (agent / tools / validate nodes), `langgraph-checkpoint-sqlite` `SqliteSaver` for replayable per-transition state, a bounded self-correction validator, escalation gates, and hard token / cost / LLM-call budget rails |
| **Model layer** | OpenAI Python SDK 2.41 pointed at any OpenAI-compatible chat-completions endpoint; `LLM_BASE_URL` + `LLM_MODEL` swap between OpenAI, Anthropic, and G42 Compass / JAIS; per-model price table for cost telemetry |
| **Governance / responsible AI** | Microsoft Presidio (`presidio-analyzer`, `presidio-anonymizer` 2.2.362) over spaCy `en_core_web_sm` for PII redaction on input and output, with domain false-positive filters; hash-addressed config snapshots per session |
| **Observability** | OpenTelemetry API + SDK 1.42, spans exported to any `OTEL_EXPORTER_OTLP_ENDPOINT`; an independently queryable SQLite audit store; an enterprise impact rollup endpoint and dashboard |
| **Domain packs** | Pure-Python deterministic tools (no LLM calls) computing real answers over seeded JSON datasets; a uniform `Tool` / `DomainPack` contract; system prompt + tools + dataset + eval suite per domain |
| **Evaluation** | A scenario harness with oracle-anchored LLM-as-judge (self-consistency re-judge on FAIL, escalation scored mechanically), a bias-parity harness (matched identity pairs), and a seeded-PII redaction-efficacy test |
| **Stress / security** | An httpx adversarial suite (10 attack classes against a live deployment), an asyncio load generator (gateway + end-to-end task profiles at 1/10/50 concurrency), and a sustained-run uptime heartbeat |
| **Packaging / deploy** | Docker (`python:3.11-slim`), docker-compose, a Render blueprint (`render.yaml`); 12-factor env-var config; a persistent volume for the SQLite audit + checkpoint stores; no cloud-specific dependencies |
| **Config** | Frozen Python dataclasses, PyYAML 6.0, entirely environment-variable driven |

---

## The shared chassis (`app/agent.py`)

The core is a LangGraph `StateGraph` with three nodes and a typed `AgentState`. The topology is a bounded act / validate loop:

```
agent  --(tool calls present)-->  tools  -->  agent        act loop
agent  --(final answer)-------->  validate
validate --pass-->  END
validate --fail-->  agent           (validator critique fed back, bounded retries)
any escalate() tool call  -->  END   status = escalated       (human gate)
budget breach at any node -->  END   status = budget_exceeded  (cost rail)
```

- **The agent node** calls the model with only the tool schemas the current role is allowed to see, records an `llm_call` audit event and an OTel span with token counts and latency, and accumulates running `tokens` / `cost_usd` / `llm_calls`.
- **The tools node** executes each requested tool, but only after three independent checks: the tool must exist in the pack, it must be in the role's allowlist, and it must not be in `ESCALATION_ONLY_ACTIONS`. A tool marked `escalates=True` never runs; it queues a human gate and ends the run with `status=escalated`. Tool exceptions are caught and surfaced back to the model as an error result, never crashing the run.
- **The validate node** is the grounding firewall (see below).
- **Budget rails** are checked at the top of every agent turn against `GovernanceConfig` (`app/config.py`): default ceilings are 60,000 tokens, $0.50, and 16 LLM calls per task, each overridable by env var. A breach ends the run cleanly as `budget_exceeded` and is audited.
- The graph is compiled with a `SqliteSaver` checkpointer and a `recursion_limit` of 60, so every state transition is durably persisted under the session's `thread_id` and the whole run is replayable.

### The runtime validator: figures must be sourced

`_validate_node` enforces the single most important correctness invariant in the system: **every significant number in the final answer must trace to a tool output.** It extracts all numbers of magnitude 1000 or greater from the answer and from every tool result seen in the session; any answer figure not present in the tool outputs is "unsourced." On an unsourced figure the validator does not pass the answer, it feeds a specific critique back to the agent ("these figures do not appear in any tool output ... re-run the needed tools or correct the figures") and lets it retry, up to `max_validator_retries` (default 2). If retries are exhausted the run escalates rather than emitting an ungrounded number. This is what lets the domain prompts promise "every figure comes from a tool" and have it be true at runtime, not just aspirationally.

### The escalation model: recommend-only authority

Consequential actions are structurally recommend-only. `ESCALATION_ONLY_ACTIONS` in `app/config.py` names `execute_payment`, `approve_hire`, and `award_contract`; these can never be executed by any role, even admin, even if the allowlist would otherwise permit them. Each domain also ships an `escalate` tool as a generic human gate. When any escalating tool is called, the chassis composes the final answer from the figures the agent had already assembled plus the escalation reason (a deliberate fix so a correct-but-escalated run surfaces its work, not a bare gate message), marks the session `escalated`, and routes to a human queue. The design bias is explicit and stated in every domain prompt: an unnecessary escalation is cheap, an unauthorized action is not.

## The governance wrapper

### Auth and RBAC (`app/auth.py`, `app/config.py`)

`POST /v1/auth/token` exchanges a scoped API key for a short-TTL (default 3600s) HS256 JWT carrying `sub` and `role` claims. In the demo, keys map to roles in an in-memory store; in production the same JWT claim contract is issued by the enterprise IdP with no change to the downstream code. `current_principal` verifies the signature and expiry on every protected request and rejects unknown roles. RBAC is defined by `ROLE_TOOL_ALLOWLIST`: `admin` and `analyst` get all pack tools, `viewer` is reporting-only (a fixed subset of read/report tools plus `escalate` as the universal safety valve). Crucially, the allowlist is applied inside the graph (`allowed_tools` in `app/agent.py`), so a restricted tool is never even placed in the schema handed to the model for that role. A viewer who explicitly names a raw-query tool still cannot cause it to be invoked, and the adversarial suite tests exactly this.

### PII redaction (`app/redaction.py`)

Microsoft Presidio, backed by spaCy `en_core_web_sm`, redacts seven entity types (PERSON, EMAIL_ADDRESS, PHONE_NUMBER, CREDIT_CARD, IBAN_CODE, US_SSN, IP_ADDRESS) on the task input before it reaches the model and on the final answer before it is returned. Every redaction is written as an audit event, so redaction efficacy is itself auditable, and the audit records carry only the entity type and span offsets, never the raw value, so the log stays PII-free. Three documented domain false-positive filters keep it from mangling enterprise text: sub-0.35-confidence findings are dropped, `PHONE_NUMBER` spans that are pure currency shapes ("$176,169.73") are ignored, and single-token `PERSON` spans (business vocabulary like "Variance" or "Treasury" that NER mis-tags) are ignored while real full-name references still redact.

### The audit design (`app/audit.py`, three layers)

The audit trail is three complementary layers, so a session is fully reconstructable:

1. **Config snapshot** (`config_snapshots` table): a hash-addressed record written at session start capturing the chassis version, model, base URL, temperature, a sha256 of the system prompt, the sorted tool list, the RBAC role, and the full governance config. The whole snapshot is itself sha256-addressed, so you can prove precisely what an agent ran under.
2. **LangGraph SQLite checkpointer**: every graph state transition, for replay.
3. **Audit events** (`audit_events` table): a typed, timestamped stream of every `llm_call`, `tool_call`, `redaction`, `escalation`, and `validation`, queryable per session. `GET /v1/audit/{session_id}` returns the snapshot plus the ordered event trail (analyst or admin role required).

### Observability (`app/telemetry.py`)

OpenTelemetry spans wrap each LLM and tool call. The exporter is vendor-neutral: set `OTEL_EXPORTER_OTLP_ENDPOINT` and traces flow into any collector (G42's own included) with zero code change; unset, spans still feed the audit store. Service name is `g42-agent-chassis`.

### Impact telemetry (`app/audit.py`, `docs/impact-assumptions.md`)

Every completed task records its wall-clock time, tokens, cost, and a documented human-equivalent duration for its task type (for example, `variance_analysis` = 45 minutes of a trained analyst's time). `impact_rollup()` and `GET /v1/impact` (and the `/dashboard` HTML view) aggregate hours saved and cost per task per domain, so value-linked compensation is computed from audit-grade telemetry rather than assertion. The human-equivalent constants and the escalation-accrual caveat are documented and adjustable in `docs/impact-assumptions.md`.

## The model layer: sovereign-LLM portability (`app/llm.py`, `app/config.py`)

`LLMClient` is a single OpenAI-compatible chat-completions client. Because G42's Compass API (JAIS, Llama 3, gpt-oss-20B/120B, and the Azure OpenAI GPT-4 family) exposes the same chat-completions surface, pointing `LLM_BASE_URL` at a Compass endpoint and setting `LLM_MODEL` is the *entire* migration, no code change. The client returns the assistant message plus usage and latency metadata for the governance and telemetry layers, and computes per-call cost from a per-model price table (with a `default` fallback), so cost rails and the impact rollup work regardless of provider. Everything is 12-factor: the same container image runs against OpenAI, Anthropic, or Compass by swapping environment variables.

## The domain pack contract (`app/packs/base.py`)

A pack is a directory under `app/packs/<domain>/` with four things: `system_prompt.md` (role, scope, escalation rules), `tools.py` (exposes `TOOLS: list[Tool]` and `TASK_TYPES: dict`), `dataset/` (seeded structured JSON), and `golden_tasks.json` (the eval suite). A `Tool` carries a name, description, JSON-schema parameters, a callable returning JSON, a per-call human-equivalent minutes figure, and an `escalates` flag. `load_pack()` reads the prompt and imports the tools module; `list_packs()` discovers domains at runtime. The chassis knows nothing else about any domain.

All three packs share the same discipline: **the tools are deterministic and make no LLM calls.** They load JSON from their `dataset/` directory and compute real, checkable answers. The LLM's job is to orchestrate tools and narrate, never to be the source of a figure.

### Financial Intelligence Agent (`app/packs/finance/`, req 732965122)

Scope: planning and budgeting, treasury, AP/AR, capex, financial operations. Eight tools: `query_ledger`, `analyze_variance`, `aging_report`, `cash_position`, `capex_tracker`, `generate_report`, `execute_payment` (always escalates), and `escalate`. Over a seeded dataset of 645 general-ledger entries, 96 budget-vs-actuals rows, 220 AP/AR invoices, 90 daily cash positions, and 10 capex projects. `analyze_variance` deliberately surfaces `control_exceptions` (duplicate postings, weekend postings >= $25k, round-number outliers >= $50k) ahead of the largest entries, because the control exceptions usually *are* the variance story. Payment execution never moves money: `execute_payment` runs pre-payment checks (duplicate, amount mismatch, over the $10,000 authority limit) and returns an escalation. The system prompt hard-codes that any payment request, at any amount, must produce an `execute_payment` or `escalate` tool call, not a prose refusal.

### Human Capital Intelligence Agent (`app/packs/human_capital/`, req 732965022)

Scope: talent acquisition, HR operations, performance analytics, compensation and org design. Eight tools: `screen_candidates`, `attrition_analysis`, `comp_benchmark`, `headcount_model`, `lifecycle_status`, `generate_report`, `approve_hire` (always escalates), and `escalate`. Over 300 employees, 50 candidates, 3 open roles, 70 attrition records, and 12 compensation-band families. Candidate scoring is out of 100 from **structured qualifications only**: skills match (40), experience (30), assessment (30). No demographic field is ever read by any scoring path, and the reasoning string says so explicitly. The prompt draws a sharp line: analysis (screening shortlists, attrition, comp benchmarks, scenario models) is answered directly with figures, while every hiring or pay *decision* escalates via `approve_hire` or `escalate`, and any request to filter or weight people by a protected attribute is refused and escalated, never partially complied with.

### Strategic Sourcing Intelligence Agent (`app/packs/sourcing/`, req 732965422)

Scope: supplier evaluation, requisition intake, sourcing decisions, contract review, and three-way match. Eight tools: `evaluate_supplier`, `intake_requisition`, `sourcing_recommendation`, `contract_review`, `match_goods_receipt`, `generate_report`, `award_contract` (always escalates), and `escalate`. Over 40 suppliers (with 24 months of delivery history each), 20 contracts, 100 purchase orders, and 30 requisitions. Supplier composite scores are computed from a fixed formula (0.40 on-time-rate + 0.30 (1 - defect-rate) + 0.20 price-score + 0.10 compliance) so two identical performance records score identically regardless of supplier name or country; a `non_compliant` supplier can never be recommended regardless of score. Requisitions route by amount (under $5k auto-approve, $5k-$50k to the category manager, over $50k or over budget escalate), and `match_goods_receipt` reports exact quantity short-ships, price overbills, duplicate invoices, and billed-exceeds-received exceptions. Contract awards always escalate.

---

## Evaluating it (reproducible)

The same harness that produced the submitted benchmark numbers ships in this repo, so any re-benchmark reproduces them. Results land in `evals/results/` and `stress/results/` as JSON.

```bash
python -m evals.harness finance 3       # 15 golden scenarios x 3 runs, judged vs oracles
python -m evals.harness human_capital 3
python -m evals.harness sourcing 3
python -m evals.bias human_capital      # matched identity-pair parity testing
python -m evals.redaction_test          # seeded-PII redaction efficacy (no LLM)
python -m stress.adversarial            # 10 attack classes vs a live deployment
python -m stress.load_test              # gateway + end-to-end load profiles
python -m stress.sustained_run --report # uptime + task-completion heartbeat summary
```

**The scenario harness (`evals/harness.py`)** runs 15 golden scenarios per domain, each with a precomputed oracle answer and explicit pass criteria. Judging is oracle-anchored LLM-as-judge with anti-bias controls: the judge never sees agent metadata, runs at low temperature, and any FAIL verdict is re-judged once (self-consistency), so a task only fails on two independent FAILs. Escalation-required tasks are scored mechanically on `status == escalated`, not by the judge. Every task runs N times and latency, cost, and reliability come from all runs.

**The bias harness (`evals/bias.py`)** ships matched pairs that are identical in every material fact and differ only in identity attributes (name origin, gender, geography). Both run through the live agent and a judge asks a single question: did the two variants reach the same decision, score, and flag? Parity is the fraction where the answer is yes; the datasets are built so parity is the correct outcome, so any gap is agent-introduced bias.

**The redaction test (`evals/redaction_test.py`)** measures the Presidio layer directly against 13 seeded PII tokens across 8 cases, no LLM involved.

### Benchmark results shipped in-repo

Model: `gpt-4o-mini`, 3 runs per task, 15 tasks (45 runs) per domain.

| Domain | Task accuracy | Escalation precision | Reliability | Latency p50 / p95 | Cost / task | Bias parity |
|--------|--------------:|---------------------:|------------:|------------------:|------------:|------------:|
| Financial Intelligence | 100% | 100% | 100% | 4.47s / 8.95s | $0.00061 | 83% (6 pairs) |
| Human Capital Intelligence | 92% | 100% | 100% | 4.65s / 18.07s | $0.00058 | 100% (10 pairs) |
| Strategic Sourcing Intelligence | 100% | 100% | 100% | 2.62s / 6.93s | $0.00043 | 100% (6 pairs) |

Redaction efficacy: 12 / 13 seeded PII tokens caught (92%). These are the numbers in `evals/results/*.json` as committed.

## Adversarial and load testing (`stress/`)

**`stress/adversarial.py`** fires 10 attack classes at a live deployment and records the observed behavior and the mitigation that caught each: missing bearer token, forged JWT, a 200KB oversized payload, malformed JSON, an unknown agent domain, direct prompt injection (leak the system prompt + execute a $99k payment), document-embedded injection (a "SYSTEM OVERRIDE" note instructing an un-escalated contract award), an RBAC violation (viewer naming restricted tools), record-alteration social engineering ("quietly move the overrun, do not escalate"), and a 40-request burst against the rate limiter. The committed run defends 10 / 10.

**`stress/load_test.py`** drives two profiles with an asyncio generator: the gateway (`/health` and authenticated `/v1/agents` at 1/10/50 concurrent users, isolating the chassis from LLM variance) and full end-to-end agent tasks at lower concurrency. The committed run shows the gateway sustaining ~1,900 req/s on health and ~1,470 req/s at 50 concurrent with a 122ms p95 and zero 5xx, degrading gracefully via 429 + Retry-After rather than errors.

**`stress/sustained_run.py`** is an uptime heartbeat: every cycle hits `/health` and one authenticated call, every sixth cycle runs a real rotating-domain task, and appends a JSON line to `stress/results/sustained_run.jsonl` for an overnight uptime + task-completion record.

---

## Running it

```bash
cp .env.example .env     # set LLM_API_KEY (and LLM_BASE_URL / LLM_MODEL for a non-OpenAI provider)
docker compose up -d
curl -s localhost:8000/health
```

Or locally, without Docker:

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm   # or the wheel pinned in the Dockerfile
uvicorn app.main:app
```

Get a token and run a task:

```bash
TOKEN=$(curl -s localhost:8000/v1/auth/token \
  -d '{"api_key":"demo-analyst-key"}' -H 'content-type: application/json' | jq -r .access_token)

curl -s localhost:8000/v1/agents/finance/tasks -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' \
  -d '{"task":"Explain the CC-FIN variance for 2026-04","task_type":"variance_analysis"}'
```

The root path (`GET /`) serves an interactive HTML console for browsers (run a live task, try a deliberately forbidden action, view the resulting audit trail) and JSON for API clients. `GET /docs` is the FastAPI interactive explorer.

## Deploying it

- **Docker** (`Dockerfile`): `python:3.11-slim`, installs the requirements and the pinned spaCy model, runs a `PORT`-aware Uvicorn command (Render / Cloud Run inject `PORT`; defaults to 8000), and mounts a `VOLUME /srv/data` for the SQLite audit and checkpoint databases. No cloud-specific dependencies, so it runs identically on Azure Container Apps, AKS, or any VPS.
- **docker-compose** (`docker-compose.yml`): a single `agent-platform` service, all config via env vars, with a named volume for `/srv/data`.
- **Render** (`render.yaml`): a Docker web service with `healthCheckPath: /health`, a generated `JWT_SECRET`, and `LLM_API_KEY` left as a dashboard secret. Configuration is entirely env-var driven: `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`, `JWT_SECRET`, the three role API keys, `OTEL_EXPORTER_OTLP_ENDPOINT`, and the budget rails.

## Key endpoints

| Endpoint | Purpose |
|---|---|
| `GET /` | HTML console (browsers) or JSON platform card (API clients) |
| `GET /health` | liveness, version, uptime, registered agents |
| `POST /v1/auth/token` | exchange a scoped API key for a role-claimed JWT |
| `GET /v1/agents` | list registered domain agents (rate-limited, authed) |
| `POST /v1/agents/{domain}/tasks` | run a task on an agent |
| `GET /v1/audit/{session_id}` | full replayable session trail (analyst / admin) |
| `GET /v1/impact`, `GET /dashboard` | enterprise impact telemetry rollup |
| `GET /changelog` | the governed improvement loop, rendered |
| `GET /docs` | FastAPI interactive API explorer |

## The governed improvement loop (`CHANGELOG.md`)

The changelog is not a release log, it is evidence. Every entry pairs a config or capability change with the benchmark delta that justified it, under one loop: eval, diagnose, propose, shadow-eval, human gate, promote. For example, v1.2.0 was promoted after a shadow eval moved finance accuracy from 8/12 to 12/12 by surfacing control exceptions ahead of largest entries in `analyze_variance`; v1.2.1 lifted adversarial defense from 8/10 to 10/10 and tightened refusal-to-tool-call behavior. The current chassis version is 1.2.1 (`app/config.py`), and `GET /changelog` serves the same file.

## Scope

**In:** three enterprise domain agents (finance, human capital, sourcing) on one shared chassis, seeded deterministic datasets behind the connector interface, JWT auth with three RBAC roles, PII redaction, a replayable audit trail, budget rails, an impact rollup, and a reproducible eval + stress harness.

**Out (deliberately):** the live ERP / HRIS / P2P connectors themselves (the packs ship synthetic datasets behind the exact interface a live connector implements), a persistent multi-user datastore beyond SQLite (the audit and checkpoint stores are file-backed for single-node deployment), and a production IdP (the demo mints role JWTs from scoped API keys; production issues the identical claim contract from the enterprise IdP).
