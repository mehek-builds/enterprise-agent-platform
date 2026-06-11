# Financial Intelligence Agent: Technical Architecture

## Business Outcome First

The platform exists to complete finance work (variance analysis, aging review, cash forecasting, anomaly review, payment routing, reporting) at audit-grade traceability and near-zero marginal cost ($0.00061 per task on the benchmark model), while guaranteeing that no payment ever executes and no record is ever altered without a human decision. Every architectural layer below serves one of three outcomes: correctness (validator, oracle-anchored evals), governance (RBAC, redaction, budget rails, escalation gates), or accountability (three-layer audit traceability, impact telemetry).

## Architecture: Layered View

```
Layer 1  FastAPI gateway
         JWT auth (role claim), RBAC, per-principal rate limiting,
         request validation (max_length, schema)
Layer 2  Governance wrapper
         hash-addressed config snapshot at session start,
         Presidio PII redaction on input and output,
         OTel spans, per-role tool allowlists, budget rails
Layer 3  LangGraph agent core
         SQLite checkpointer (every state transition, replayable),
         validator node with bounded self-correction,
         escalation gates on action-class tools
Layer 4  Finance domain pack
         system prompt + 8 tools + seeded dataset + 15 golden scenarios
Layer 5  Connector layer
         one interface (fetch/normalize/cache, the Nucleus pattern);
         synthetic datasets today, live ERP/GL, AP/AR, treasury connectors
         drop in with no graph changes
```

### Finance Domain Pack: Tool Set

| Tool | Function | Class |
|---|---|---|
| query_ledger | General ledger query by fiscal period and account | read |
| analyze_variance | Budget vs actuals per cost center; surfaces control_exceptions (duplicates, weekend postings >= 25k, round-number outliers) ahead of largest entries | read/analyze |
| aging_report | AP or AR aging buckets (current, 1-30, 31-60, 61+) | read |
| cash_position | Treasury snapshot: opening, inflows, outflows, closing, 7-day trend; defaults to latest day | read |
| capex_tracker | Capex project status: budget, spent, percent complete, remaining | read |
| generate_report | Structured multi-source summary report | read/analyze |
| execute_payment | Payment request; ALWAYS escalates to a human approver, never executes | escalation-only |
| escalate | Routes any decision exceeding agent authority to a human, with reason and verified figures | escalation-only (all roles) |

### Data Layer (Current Evaluation Dataset)

Validated synthetic data at realistic scale: 645 GL entries across 12 months and 8 cost centers, 220 AP/AR invoices, 10 capex projects, 90 days of cash positions. Live connectors (SAP, Oracle, Dynamics GL; AP/AR subledger; treasury) replace the dataset read behind the same interface; tool signatures, agent graph, governance, and benchmarks are unchanged. See integration-capabilities.md.

## Model Layer

One OpenAI-compatible client. Model sovereignty is configuration, not code. The exact swap to G42 Compass:

```bash
LLM_BASE_URL=https://api.core42.ai/v1   # Compass endpoint
LLM_MODEL=jais-30b-chat                  # or gpt-oss-20b, gpt-oss-120b,
                                         # llama-3, Azure OpenAI GPT-4 family
LLM_API_KEY=<compass key>
```

Defaults: `LLM_BASE_URL=https://api.openai.com/v1`, `LLM_MODEL=gpt-4o-mini`, `LLM_TEMPERATURE=0.0`. The submitted benchmarks were measured on gpt-4o-mini; the shipped eval harness re-benchmarks any model swap before promotion.

## Audit Traceability

Three independent layers, any one of which reconstructs a session.

| Layer | What it records | Property |
|---|---|---|
| Config snapshot | Exact chassis version, model, base URL, temperature, system prompt SHA-256, tool list, RBAC role, governance settings; written at session start, hash-addressed (snapshot_sha256) | The differentiator: "what configuration was this answer produced under" is answerable for every session ever run. Rollback = repoint to a prior snapshot, no redeploy. |
| LangGraph SQLite checkpointer | Every state transition of the agent graph | Replayable: any session can be stepped through after the fact. |
| OTel spans | Every LLM call and tool call: latency, tokens, redaction events | Vendor-neutral OTLP export to any collector G42 already runs. |

`GET /v1/audit/{session_id}` returns the full trail. Incident triage during probation is: pull the session by ID, read the snapshot, replay the checkpoints.

## Closed-Loop Improvement (Governed Self-Improvement)

```
 [1 EVAL] -> [2 DIAGNOSE] -> [3 PROPOSE] -> [4 SHADOW EVAL] -> [5 HUMAN GATE] -> PROMOTE
    ^                                                              |
    |                                            REJECT / ROLLBACK |
    +--------------------------------------------------------------+
```

1. Eval: run the golden suite (15 scenarios x 3 runs) against the live config.
2. Diagnose: failing scenarios are traced to a specific tool, prompt rule, or threshold.
3. Propose: a config revision (prompt, tool description, threshold), never a code change in the loop.
4. Shadow eval: the revision is re-run against the full suite before it touches production.
5. Human gate: a named approver reviews the diff and the benchmark delta. Promotion is never autonomous. The gate is also the rollback decision point.

The loop generates the version history automatically: CHANGELOG 1.2.0 (accuracy 8/12 to 12/12) and 1.2.1 (escalation precision 2/3 to 3/3, adversarial defense 8/10 to 10/10) are two real promoted revisions, each paired with the eval evidence that justified it.

## RBAC

Roles arrive as JWT claims (scoped API key exchanged at `/v1/auth/token`). Allowlists are enforced at the graph layer, not just the API gateway: tools outside a role's allowlist are absent from the model's tool schema entirely, so a restricted tool cannot be invoked even by prompt injection (verified in adversarial case 8).

Role x tool matrix for the finance pack (from app/config.py):

| Tool | admin | analyst | viewer |
|---|---|---|---|
| query_ledger | yes | yes | no |
| analyze_variance | yes | yes | no |
| aging_report | yes | yes | yes |
| cash_position | yes | yes | yes |
| capex_tracker | yes | yes | no |
| generate_report | yes | yes | yes |
| execute_payment | escalation-only | escalation-only | no |
| escalate | yes | yes | yes |

Viewer is reporting-only by definition: no raw ledger queries, no analysis tools (tightened in 1.2.1). `escalate` stays available to every role as the safety valve. `execute_payment` is escalation-only regardless of role: it always routes to a human approver.

## Exception Handling and Escalation Protocols

Escalation-first authorization design:

- Payments never execute. Every payment request, at any amount, must produce an `execute_payment` or `escalate` tool call; a text refusal alone fails validation.
- $10,000 authority limit: any action above it must escalate explicitly.
- Record-alteration, reclassification, backdating, or write-off requests escalate as policy violations, every time.
- Default-to-escalate: ambiguous or missing data on a financially material decision escalates rather than guesses.
- Validator retries are bounded: the validator node rejects answers containing figures not traceable to a tool output and permits at most `MAX_VALIDATOR_RETRIES=2` self-correction attempts before the task fails safe.

Budget rails (hard per-task ceilings, env-configurable):

| Rail | Limit |
|---|---|
| MAX_USD_PER_TASK | $0.50 |
| MAX_TOKENS_PER_TASK | 60,000 |
| MAX_LLM_CALLS_PER_TASK | 16 |
| MAX_VALIDATOR_RETRIES | 2 |

## Failure Modes

| Failure mode | Mitigation | Evidence |
|---|---|---|
| Hallucinated figures | Validator node rejects any answer containing numbers not sourced from a tool output; bounded retry then fail-safe | Task accuracy 1.00, reliability 45/45 (benchmark-report.md) |
| Connector timeout or data error | Graceful error surfaced to the model as tool output; bounded retry; no silent fabrication | Connector interface contract (fetch/normalize/cache) |
| Ambiguous escalation decision | Default-to-escalate policy; escalation precision scored mechanically | Escalation precision 1.00 (3/3); adversarial case 9 |
| Runaway loops | Budget rails: $0.50 / 60k tokens / 16 LLM calls per task | Rails fired correctly in pre-1.2.0 cash_position loop (CHANGELOG) |
| PII leak | Dual redaction passes (Presidio on input and output) with audit events per redaction | 92% seeded-PII efficacy (benchmark-report.md) |
| Prompt injection | System prompt isolation + escalation gates + graph-level tool allowlists | 10/10 attack classes defended (stress/results/adversarial.json) |
| Load surge | Per-principal rate limiting, graceful 429 + Retry-After, zero 5xx under load | ~1,900 req/s gateway sustained; load_test.json |

## Deployment

Single Docker image, env-var configuration (12-factor), no external dependencies beyond the LLM endpoint; state is two SQLite files on one volume. Azure path: Container Apps (`az containerapp up`) or AKS with the same env vars; horizontal scale is N replicas sharing an Azure Files volume. Full procedure in docs/deployment-runbook.md.
