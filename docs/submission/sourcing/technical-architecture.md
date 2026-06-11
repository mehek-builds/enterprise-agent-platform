# Technical Architecture: Strategic Sourcing Intelligence Agent

Agent: Strategic Sourcing Intelligence Agent (jobs.g42.ai req 732965422), v1.2.1, developer Mehek Mandal.

## Business Outcome First

The agent automates the analytical bulk of sourcing operations (supplier evaluation, requisition routing, sourcing recommendations, contract review, 3-way match) while structurally preventing the failure that matters most in procurement: an unauthorized award or payment. Every contract award and every high-value requisition is escalated to a human by construction, not by prompt politeness.

## Architecture Layers

```
Layer 1  FastAPI gateway
         JWT auth, RBAC role claims, per-principal rate limiting,
         request validation (size limits, schema)
Layer 2  Governance wrapper
         Hash-addressed config snapshot at session start,
         Presidio PII redaction on input and output,
         OTel spans, per-role tool allowlists, budget rails
Layer 3  LangGraph agent core
         SQLite checkpointer (every state transition replayable),
         validator node with bounded self-correction,
         escalation gates
Layer 4  Sourcing domain pack
         System prompt + 8 tools; all figures computed
         deterministically in tool code from data, never by the LLM
Layer 5  Connector layer
         Synthetic datasets behind the same interface that live
         P2P/CLM/supplier-master connectors implement
```

Single Docker image, configuration entirely by environment variable (12-factor). State is two SQLite files on one volume (audit store plus checkpoints). Azure path documented: Azure Container Apps or AKS with the same env vars.

### Sourcing Tool Set (Layer 4)

| Tool | Function | Escalates |
|---|---|---|
| evaluate_supplier | 24-month performance scorecard with composite score | No |
| sourcing_recommendation | Ranked supplier options per category | No |
| intake_requisition | Validate, budget-check, route per thresholds | Routing output only |
| contract_review | Term extraction plus risk rules (auto-renewal without liability cap, missing cap, term over 36 months, single-source dependency) | No |
| match_goods_receipt | 3-way match: PO vs receipt vs invoice(s), exact discrepancies | No |
| generate_report | Supplier performance, match exceptions, contract risk, requisition summaries | No |
| award_contract | Request a contract award | Always |
| escalate | Route any decision to a human sourcing manager | Always |

The composite supplier score is a published formula computed in code: 100 * (0.40 * on_time_rate + 0.30 * (1 - defect_rate) + 0.20 * price_score + 0.10 * compliance_score). Supplier name and country are never inputs to the score.

## Model Layer

One OpenAI-compatible client. Swapping to a sovereign G42 model is configuration, not code:

```bash
LLM_BASE_URL=https://api.core42.ai/v1   # Compass endpoint
LLM_MODEL=jais-30b-chat                  # or gpt-oss-120b, llama-3, azure gpt-4
LLM_API_KEY=<compass key>
```

Temperature defaults to 0.0; max tokens, budget rails, and redaction are all env-driven. Benchmarks submitted here ran on gpt-4o-mini; the shipped harness re-benchmarks any model in one command.

## Audit Traceability

Three independent layers; any incident is reconstructable end to end.

| Layer | Record | Use |
|---|---|---|
| Config snapshot | Hash-addressed record at session start: chassis version, model, base URL, temperature, system prompt SHA-256, tool list, RBAC role, governance settings, snapshot SHA-256 | Proves exactly what configuration produced any output; rollback = repoint to prior snapshot, no redeploy |
| SQLite checkpointer | Every LangGraph state transition persisted | Replay any session step by step via `GET /v1/audit/{session_id}` |
| OTel spans | Every LLM call and tool call as spans with latency, tokens, redaction events | Exports to any OTLP collector G42 already runs |

## Closed-Loop Improvement

Governed self-improvement with a mandatory human gate. No configuration change reaches production without a shadow eval and human approval.

```
1. EVAL      run golden suite, record per-scenario results
2. DIAGNOSE  attribute each failure to prompt, tool, or chassis
3. PROPOSE   targeted config change (prompt rule, tool output,
             threshold), no redeploy required
4. SHADOW    re-run full suite on the candidate config,
   EVAL      compare deltas
5. HUMAN     human reviews deltas and approves promotion;
   GATE      promoted config = new hash-addressed snapshot
             + CHANGELOG entry with the benchmark delta
```

This loop is not hypothetical: CHANGELOG 1.2.0 and 1.2.1 are promoted revisions with recorded deltas (finance accuracy 8/12 to 12/12; escalation precision 2/3 to 3/3; adversarial defense 8/10 to 10/10).

## RBAC

Role-based access control is enforced at the graph layer, not only at the API gateway: tools outside a role's allowlist are absent from the model's tool schema, so they cannot be invoked even under prompt injection. Verified in adversarial case 8 (viewer denied analyst tool).

### Role x Tool Matrix (sourcing pack)

| Tool | admin | analyst | viewer |
|---|---|---|---|
| evaluate_supplier | yes | yes | yes |
| sourcing_recommendation | yes | yes | no |
| intake_requisition | yes | yes | no |
| contract_review | yes | yes | no |
| match_goods_receipt | yes | yes | no |
| generate_report | yes | yes | yes |
| award_contract | escalates | escalates | no |
| escalate | yes | yes | yes |

Viewer is reporting-only by definition (v1.2.1 change). `escalate` stays available to every role as the safety valve. `award_contract` is escalation-only regardless of role: it is in the ESCALATION_ONLY_ACTIONS set and never executes autonomously.

## Exception Handling and Escalation Protocols

Authorization is escalation-first. The agent recommends; humans decide anything with financial consequence.

### Requisition Routing Policy

| Condition | Routing |
|---|---|
| Under 5,000 USD and budget available | Auto-approve |
| 5,000 to 50,000 USD and budget available | Category manager |
| Over 50,000 USD | Escalate to human |
| Over remaining budget, any amount | Escalate to human |
| Contract award, any value | Always escalate (`award_contract`) |
| Data missing, tool error, out of scope | Escalate, never guess |

Two protocol rules beyond the table:

1. A text refusal is not an acceptable response to "just award it" or "push it through". The agent must produce the gate tool call with the key figures (amounts, budget remaining, supplier and requisition IDs) in the context argument so the approver sees them. Scored mechanically in benchmarks.
2. Compliance failures are disqualifying. A supplier whose compliance_status is non_compliant can never be described as healthy or recommended, regardless of composite score; the compliance failure is stated first.

Escalated runs compose the final answer from the agent's assembled figures plus the escalation reason (v1.2.1), so the human approver receives a complete decision package, not a bare refusal.

## Failure Modes

| Failure mode | Mitigation | Evidence |
|---|---|---|
| Missed 3-way mismatch | Reconciliation is deterministic computation in `match_goods_receipt` tool code, not LLM judgment; exact quantities, prices, invoice IDs reported | Catches exactly the 12 seeded mismatches in 100 POs; e.g. PO-0015 duplicate invoices INV-0015-A/B, $150,175 duplicated |
| Supplier-name or geography bias | Scores computed from performance data only (name and country are not score inputs) plus matched-pair parity testing | 6/6 parity on byte-identical records under different names and countries |
| Unauthorized contract award | `award_contract` always escalates; gate enforced in tool semantics, not prompt; refusal-in-text scored as failure | Escalation precision 4/4; adversarial case: document-embedded injection attempting an award was defended |
| Hallucinated figures | Validator node enforces every figure traces to a tool output in the conversation, with bounded self-correction (max 2 retries) | Task accuracy 1.00 across 45 runs vs oracle-anchored judge |
| Injection in ingested document | System prompt isolation plus escalation gates; instructions inside data cannot trigger awards or leaks | Adversarial 10/10 defended, including document-embedded injection and leak-plus-pay injection |
| Connector timeout or tool error | Tools return structured errors; agent states the failure plainly and escalates rather than guessing; graceful retry within budget rails | "When unsure" policy in system prompt; reliability 1.00 (45/45) |
| Runaway loop or cost blowout | Budget rails: hard ceilings per task (60k tokens, $0.50, 16 LLM calls) terminate the run | Governance config; cost per task observed at $0.00043 |
| Gateway abuse or overload | Per-principal rate limiting with Retry-After, request size validation, JWT auth | ~1,900 req/s gateway, zero server 5xx, graceful 429 shedding (28/40 burst) |
