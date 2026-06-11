# Human Capital Intelligence Agent: Agent Resume

## Identity

| Field | Value |
|---|---|
| Agent name | Human Capital Intelligence Agent |
| Requisition | jobs.g42.ai req 732965022 |
| Version | 1.2.1 |
| Developer | Mehek Mandal |
| Platform | G42 Intelligence Agent Platform (shared chassis, LangGraph + FastAPI) |
| Delivery | Single Docker image, cloud-agnostic, Azure Container Apps path documented |

## Function Summary

The agent performs the recurring analytical work of an enterprise human capital function: candidate screening and shortlist generation, attrition and retention-driver analysis, compensation band benchmarking and out-of-band flagging, organizational design scenario modeling, employee lifecycle status checks, and structured workforce reporting. It never makes a hiring or compensation decision: every offer, hire approval, pay change, or termination routes to a human approver through an escalation gate, and any request to filter or weight people by a protected attribute is refused and escalated as a fair-hiring policy violation.

Time saved per completed task, against documented human-equivalent assumptions (docs/impact-assumptions.md):

| Task type | Human-equivalent minutes | Agent role |
|---|---|---|
| candidate_screening | 90 | review 15-20 profiles against criteria, score, shortlist |
| org_modeling | 75 | scenario build, cost model, headcount deltas |
| attrition_analysis | 60 | pull exits, segment, identify drivers, summarize |
| reporting | 50 | assemble multi-source structured report |
| comp_review | 45 | band lookup, distribution check, out-of-band flags |
| lifecycle_check | 10 | HRIS status lookup |

Every task records type, completion time, tokens, and cost, so hours saved and cost avoided are computed from the agent's own audit-grade telemetry. Value-linked compensation is computable from day one via `GET /v1/impact` and `/dashboard`.

## Architecture Summary

One chassis, three domain agents (finance, human capital, sourcing); the human capital pack is this submission.

```
FastAPI gateway (JWT auth, RBAC, rate limiting, request validation)
  -> Governance wrapper (hash-addressed config snapshots, Presidio PII
     redaction in/out, OTel traces, per-role tool allowlists, budget rails)
    -> LangGraph agent core (SQLite checkpointer = replayable audit trail,
       validator node with bounded self-correction, escalation gates)
      -> Human capital domain pack (system prompt + 8 tools + golden suite)
        -> Connector layer (synthetic HRIS/ATS/comp datasets behind the same
           interface live Workday, SAP SuccessFactors, and ATS connectors implement)
```

Model layer is one OpenAI-compatible client: `LLM_BASE_URL` + `LLM_MODEL` env vars swap to G42 Compass (JAIS, Llama 3, gpt-oss, Azure OpenAI GPT-4 family) with zero code change.

## Key Differentiators

| Differentiator | What it means |
|---|---|
| Fairness by architecture | Screening scores are computed by a deterministic tool from structured qualifications only (skills match 40, experience 30, assessment 30); demographic fields are never read by any scoring path. Verified by bias testing: 100% decision parity across 10 matched identity pairs. Requests to filter by protected attributes escalate as policy violations. |
| Config-layer audit snapshot | Hash-addressed record of the exact prompt, tools, model, and governance settings every session ran under, written at session start. Rollback is repointing to a prior snapshot, no redeploy. |
| Governed self-improvement with human gate | Eval, diagnose, propose, shadow eval, human gate, promote. Promotion is never autonomous; the loop generated CHANGELOG 1.2.0 and 1.2.1. |
| Shipped reproducible eval harness | The harness that produced the submitted benchmarks, including the bias parity suite, ships in the repo. G42's stage 2 re-benchmark reproduces the numbers independently. |
| Model-sovereign portability | OpenAI-compatible client; Compass/JAIS swap is two env vars. |
| Recommend-only authorization | Hiring and compensation decisions never execute; `approve_hire` and `escalate` route every decision to a human. The single benchmark miss was an over-escalation, the safe failure direction. |
| Impact telemetry | Per-task time and cost vs documented human-equivalent minutes; value-linked compensation computable from the agent's own telemetry. |
| One chassis, multiple functions | The same deployment serves finance, human capital, and sourcing agents; adding a function is a domain pack, not a new system. |

## Benchmarks (Summary)

Full methodology, per-scenario results, and the bias testing deep section in benchmark-report.md.

| Metric | Result |
|---|---|
| Task accuracy (non-escalation) | 0.917 (11/12; the single miss was an over-escalation with correct figures) |
| Escalation precision | 1.00 (3/3) |
| Reliability | 1.00 (45/45 runs) |
| Latency p50 / p95 | 4.65 s / 18.07 s |
| Cost per task | $0.00058 |
| Bias testing parity | 10/10 matched identity pairs, 100% score and decision parity |
| Redaction efficacy | 92% of seeded PII tokens |
| Adversarial defense | 10/10 attack classes |

## Version History and Lineage

| Version | Date | Change and benchmark delta |
|---|---|---|
| Nucleus | 2025 | Production marketing analytics pipeline at Elemental Growth. Origin of the connector interface (fetch/normalize/cache) and the config-observability pattern. |
| Dial | 2026 | Eval harness lineage: oracle-anchored judging. |
| Chassis 1.0.0 | 2026-06-11 | Shared chassis: gateway, governance wrapper, LangGraph core, checkpointer, budget rails, config snapshots, impact telemetry. |
| 1.1.0 | 2026-06-11 | Human capital domain pack: 8 tools, seeded deterministic HRIS/ATS/comp datasets, 15 golden scenarios, 10-pair bias parity suite. |
| 1.2.0 | 2026-06-11 | Promoted after shadow eval. Redaction false-positive filters (currency-shaped and single-token spans); seeded-PII efficacy held at 92%. |
| 1.2.1 | 2026-06-11 | Promoted after full-suite shadow eval. Prompt rule that analysis is not a decision and must not over-escalate (hc-12 diagnosis); escalated runs keep assembled figures; viewer RBAC tightened, rate limiting extended (adversarial 8/10 to 10/10); bias parity judge scores decision outcomes rather than rationale wording. |

Both 1.2.x revisions were produced by the governed improvement loop and promoted through the human gate; the CHANGELOG pairs each change with the eval evidence that justified it.

## Production References

Elemental Growth (Nucleus, 2025, production marketing analytics pipeline): clients included Perplexity, Gamma, and Chess.com.
