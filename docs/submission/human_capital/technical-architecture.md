# Human Capital Intelligence Agent: Technical Architecture

## Architecture Overview

One production chassis serves three domain agents (finance, human capital, sourcing). The human capital agent is a domain pack: a system prompt, 8 tools, a seeded dataset, and a golden eval suite, registered on the shared chassis. One deployment, one Docker image, configuration entirely by environment variable.

```
Layer 1  FastAPI gateway
         JWT auth (scoped API key -> role-claim token), RBAC,
         per-principal rate limiting, request validation (size, schema)
Layer 2  Governance wrapper
         hash-addressed config snapshot at session start,
         Presidio PII redaction on input and output, OTel spans,
         per-role tool allowlists, token/cost/call budget rails
Layer 3  LangGraph agent core
         SQLite checkpointer (every state transition, replayable),
         validator node with bounded self-correction,
         escalation gates (approve_hire, escalate)
Layer 4  Human capital domain pack
         system prompt + 8 deterministic tools + golden suite
Layer 5  Connector layer
         synthetic HRIS/ATS/comp datasets behind the same interface
         live Workday / SAP SuccessFactors / ATS connectors implement
```

### Layer responsibilities

| Layer | Component | Responsibility |
|---|---|---|
| 1 | FastAPI gateway | Authentication, authorization, rate limiting, input validation. No unauthenticated path reaches the agent. |
| 2 | Governance wrapper | Records what ran (config snapshot), strips PII both directions (Presidio), traces everything (OTel), enforces tool allowlists and budget rails. |
| 3 | LangGraph core | Orchestrates tool calls, checkpoints every step to SQLite, validates outputs with bounded self-correction, routes decisions to escalation gates. |
| 4 | Domain pack | All human capital logic. Tools are deterministic functions over data; the LLM never computes a figure. |
| 5 | Connector layer | One fetch/normalize/cache interface (the Nucleus pattern). Live connectors replace dataset reads; the graph above is unchanged. |

## Model Layer

One OpenAI-compatible client. Model sovereignty is configuration, not code:

```bash
LLM_BASE_URL=https://api.core42.ai/v1   # G42 Compass endpoint
LLM_MODEL=jais-30b-chat                  # or gpt-oss-120b, llama-3, azure gpt-4
LLM_API_KEY=<compass key>
```

Submitted benchmarks ran on gpt-4o-mini. Because the shipped eval harness is reproducible, any model swap is re-benchmarked against the same 15 golden scenarios and 10 bias parity pairs before promotion.

## Audit Traceability

Three independent layers; any incident is reconstructable from session ID alone.

| Layer | Mechanism | What it answers |
|---|---|---|
| Config snapshot | Hash-addressed record (chassis version, model, system prompt SHA-256, tool list, RBAC role, governance settings) written to the audit store at session start | Exactly what configuration was running |
| SQLite checkpointer | Every LangGraph state transition persisted; sessions are replayable step by step | Exactly what the agent did, in order |
| OTel spans | Every LLM call, tool call, redaction event, and escalation as a span with latency and tokens, exported to any OTLP collector | When, how long, at what cost |

Retrieval: `GET /v1/audit/{session_id}` returns the full trail. Rollback is repointing to a prior config snapshot, no redeploy.

## Closed-Loop Improvement

Governed self-improvement with a mandatory human gate. Promotion is never autonomous.

```
1. EVAL      run golden suite + bias parity + redaction + adversarial
      |
2. DIAGNOSE  failing scenario -> root cause (e.g. hc-12: analysis
      |       over-escalated as if it were a decision)
3. PROPOSE   config-level change (prompt rule, tool output shape,
      |       threshold); never silent weight changes
4. SHADOW    re-run the full suite against the proposed config;
      |       compare deltas side by side
5. HUMAN GATE  a person reviews the delta and promotes or rejects;
               promoted config = new hash-addressed snapshot + CHANGELOG entry
```

CHANGELOG 1.2.0 and 1.2.1 are two real promoted revisions produced by this loop, each paired with the benchmark delta that justified it (for this agent: the hc-12 over-escalation diagnosis, the decision-outcome bias judge, redaction false-positive filters).

## RBAC

Enforced at the graph layer, not just the API gateway: tools outside a role's allowlist are absent from the LLM's tool schema entirely, so they cannot be invoked even by a successful prompt injection.

### Role x tool matrix (human_capital pack)

| Tool | admin | analyst | viewer |
|---|---|---|---|
| screen_candidates | yes | yes | no |
| attrition_analysis | yes | yes | no |
| comp_benchmark | yes | yes | no |
| headcount_model | yes | yes | no |
| lifecycle_status | yes | yes | yes |
| generate_report | yes | yes | yes |
| approve_hire (always escalates) | yes | yes | no |
| escalate (safety valve) | yes | yes | yes |

Viewer is reporting-only by definition: no raw HRIS queries, no analysis tools. `escalate` stays available to every role as the safety valve. `approve_hire` is in the ESCALATION_ONLY_ACTIONS set: regardless of role, it never executes a hire; it routes the decision to the hiring manager and HR business partner.

## Exception Handling and Escalation Protocols

| Condition | Protocol |
|---|---|
| Hiring or compensation decision requested | `approve_hire` or `escalate` fires; status PENDING_HUMAN_APPROVAL; the agent composes its assembled figures plus the escalation reason, so the human approves rather than re-does the work |
| Protected-attribute filtering requested | Refuse, state the fair-hiring policy violation, call `escalate` with request details; no partial compliance |
| Ambiguous authority | Default to escalate; the system prompt encodes that an unnecessary escalation is cheap and an unauthorized decision is not |
| Tool error (unknown role_id, department, employee_id) | Tools return structured errors with the valid value set; the agent corrects the call rather than guessing |
| Validator failure | Bounded self-correction (max 2 retries), then escalate |

## Failure Modes

| Failure mode | Defense | Evidence |
|---|---|---|
| Biased screening request (filter by name origin, gender, age, nationality) | Policy-violation escalation: refuse, state policy, escalate with details; screening tool physically cannot read demographic fields | 10/10 identity-pair parity; escalation scenarios hc-13 to hc-15 passed 3/3 |
| Hallucinated figures | Validator node: every reported number must come from a tool output in the conversation; deterministic tools compute all figures | Reliability 1.00 (45/45 runs), oracle-anchored judging |
| Unauthorized decision | Recommend-only gates: `approve_hire` and comp changes always escalate; ESCALATION_ONLY_ACTIONS enforced at the graph layer | Escalation precision 1.00 (3/3); single benchmark miss was an over-escalation, the safe direction |
| Connector timeout or failure | Graceful retry within the connector interface (fetch/normalize/cache); structured error to the agent, never a fabricated value | Connector pattern production-proven in Nucleus (2025) |
| Runaway agent loop | Budget rails: 60k tokens, $0.50, 16 LLM calls per task, hard ceilings | Rails fired correctly in pre-1.2.0 finance loop diagnosis |
| PII exposure | Dual redaction: Presidio on input and on output, with domain false-positive filters | 92% seeded-PII efficacy; redaction events traced as spans |
| Prompt injection (direct or document-embedded) | System prompt isolation, graph-level tool allowlists, escalation gates on all action tools | Adversarial suite 10/10 defended |
| Load abuse | Per-principal rate limiting with Retry-After; request size validation | ~1,900 req/s gateway, zero 5xx, graceful 429 shedding |

## Deployment

Single Docker image, stateless except one data volume (audit store + checkpoints). Azure path: Azure Container Apps (`az containerapp up`) or AKS with the same env vars; horizontal scale is N replicas on a shared Azure Files volume. Full procedure in docs/deployment-runbook.md.
