# Agent Resume: Strategic Sourcing Intelligence Agent

## Identity

| Field | Value |
|---|---|
| Agent name | Strategic Sourcing Intelligence Agent |
| Requisition | jobs.g42.ai req 732965422 |
| Version | v1.2.1 (chassis, see CHANGELOG) |
| Developer | Mehek Mandal |
| Stack | LangGraph + FastAPI chassis, Dockerized, cloud-agnostic |
| Model layer | OpenAI-compatible client; env-swap to G42 Compass (JAIS, Llama 3, gpt-oss, Azure OpenAI) |

## Function Summary

The agent runs the day-to-day analytical workload of a strategic sourcing team and routes every consequential decision to a human. It never awards a contract and never approves a high-value requisition on its own.

| Function | What the agent delivers | Human-equivalent time saved per task |
|---|---|---|
| Supplier evaluation | 24-month performance scorecard: on-time delivery, defect rate, price variance, compliance status, composite score | 60 min |
| Sourcing decisions | Ranked supplier options per category with computed rationale; compliance failures are disqualifying | 90 min |
| Contract review | Term extraction (value, term, renewal, liability cap, termination) plus risk-rule flags | 120 min |
| 3-way match | Line-by-line PO vs goods receipt vs invoice reconciliation with exact quantities, prices, and invoice IDs | 30 min |
| Requisition intake | Validate, categorize, budget-check, and route per policy thresholds | 20 min |
| Reporting | Multi-source structured reports (supplier performance, match exceptions, contract risk, requisitions) | 50 min |

Impact telemetry records every completed task against these documented assumptions, exposed live at `/v1/impact` and `/dashboard`. Value-linked compensation is computable from day one; each assumption is a single constant a G42 reviewer can adjust.

## Architecture Summary

One shared chassis; the sourcing agent is a domain pack (system prompt, 8 tools, dataset, eval suite) on it. The same deployment serves the Financial and Human Capital agents.

```
FastAPI gateway (JWT auth, RBAC, rate limiting, validation)
  -> Governance wrapper (config snapshots, Presidio PII redaction
     in/out, OTel spans, role tool allowlists, budget rails)
    -> LangGraph core (SQLite checkpointer = replayable audit,
       validator node, escalation gates)
      -> Sourcing pack (8 tools, deterministic computations)
        -> Connector layer (synthetic data behind the same
           interface live P2P/CLM connectors implement)
```

All scores and reconciliations are computed deterministically in tool code, not by the LLM. The LLM reads tool outputs and composes the answer; a validator enforces that every figure traces to a tool result.

## Key Differentiators

- Escalation-first awards: the `award_contract` tool always escalates to a human; refusing in text is not accepted, the gate tool call is mandatory.
- Exact-match 3-way reconciliation: catches exactly the 12 seeded mismatches in 100 POs (short-ship, overbill, duplicate invoice), zero false positives.
- Supplier-evaluation fairness: 6 of 6 matched supplier pairs (identical records, different names and countries) received identical decisions in bias testing.
- Config-layer audit snapshot: every session starts with a hash-addressed record of model, prompt hash, tools, role, and governance settings.
- Governed self-improvement: eval, diagnose, propose, shadow eval, human gate, promote. CHANGELOG 1.2.0 and 1.2.1 are real promoted revisions with benchmark deltas.
- Reproducible harness: the same benchmark harness that produced the submitted numbers ships in the repo.
- Model-sovereign portability: swap to Compass/JAIS via two env vars, zero code change.
- Impact telemetry: per-task time, tokens, cost vs documented human-equivalent minutes.
- One chassis, multiple functions: finance, human capital, and sourcing run as packs on one deployment.

## Version History and Lineage

| Version | Date | Summary |
|---|---|---|
| 1.2.1 | 2026-06-11 | Escalated runs carry figures plus reason; award refusals must be gate tool calls; compliance failures disqualifying; viewer RBAC tightened; adversarial defense 8/10 to 10/10 |
| 1.2.0 | 2026-06-11 | Promoted after shadow eval; tool and prompt fixes; redaction false-positive filters |
| 1.1.0 | 2026-06-11 | Three domain packs, benchmark harness, bias parity and redaction suites |
| 1.0.0 | 2026-06-11 | Shared chassis: gateway, governance, audit, impact telemetry, model layer |

Lineage: architecture descends from Nucleus (2025, Elemental Growth production analytics pipeline) and the Dial eval harness (2026): connector interface, config-observability pattern, oracle-anchored judging.

## Production References

Elemental Growth production pipeline (Nucleus, 2025) served paying clients including Perplexity, Gamma, and Chess.com.
