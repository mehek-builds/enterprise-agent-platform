# 30-60-90 Day Probationary Deployment Plan

## Business Outcome First

By day 90 the Financial Intelligence Agent operates under supervised autonomy on live G42 finance data, with every expansion of authority justified by a defined metric threshold, every configuration change promoted through a human gate, and impact (hours saved, cost avoided) computed from the agent's own audit-grade telemetry. The plan is deliberately escalation-first: authority is earned by evidence, never assumed.

## Architecture of the Rollout

The same chassis runs in all three phases; only the authorization posture and the data sources change. Audit traceability (config snapshots, replayable checkpoints, OTel spans) is identical from day 1, so every phase produces the evidence the next phase's go decision requires.

## Days 1-30: Shadow Mode

The agent runs alongside the existing human workflow. No agent output reaches a decision unreviewed.

- Deploy the Docker image to Azure Container Apps; point the model layer at G42 Compass (env-var swap); connect read-only ERP/GL, AP/AR, and treasury connectors through the connector interface.
- Run live tasks in parallel with the human process; finance staff continue as-is.
- Impact telemetry baselines: per-task completion time, tokens, cost vs the documented human-equivalent minutes; calibrate the escalated-task triage fraction against observed approver time.
- Build the live-data golden set: port the 15-scenario suite to live connector data with oracles signed off by G42 finance.
- Weekly eval reports from the shipped harness (accuracy, escalation precision, latency, cost, bias parity, redaction efficacy) delivered to the G42 reviewer.

Exit criteria: live-data golden set established, four weekly eval reports delivered, zero unsourced-figure incidents in shadow output.

## Days 31-60: Supervised Autonomy

Agent output is used, with humans approving every consequential action.

- Escalation gates active: payments, above-authority actions, anomalies, and record-alteration requests route to named approvers with defined approver SLAs (target: same business day).
- Agent handles variance analysis, aging review, cash forecasting, anomaly review, and reporting end to end; approvers review escalations rather than redoing the analysis.
- Configuration revisions (prompt rules, thresholds, tool descriptions) flow exclusively through the governed improvement loop: eval, diagnose, propose, shadow eval, human gate, promote. Each promotion lands as a CHANGELOG entry with its benchmark delta.
- Weekly eval reports continue on the live-data golden set; bias and redaction suites re-run on every promoted revision.
- Approver feedback captured per escalation (correct to escalate: yes/no) to score escalation precision on live traffic.

Exit criteria: the day-61 metric thresholds below, measured over the days 31-60 window.

## Days 61-90: Scaled Authorization

Authority expands only where the metrics justify it.

- Expand task volume and cost-center coverage; raise the share of finance reporting produced agent-first.
- Evaluate raising specific authority boundaries (for example, recommend-and-queue below the $10,000 limit with batch approval) as a human-gated config revision, only if the day-61 thresholds held.
- Onboard the second domain pack (Human Capital or Sourcing) on the same deployment if G42 elects: one chassis, no new infrastructure.
- Produce the day-90 impact report from `/v1/impact`: hours saved, cost per task vs human-equivalent cost, escalation quality, full audit coverage statement.

## Metrics and Thresholds for Expansion

| Metric | Threshold to justify expanded authorization | Source |
|---|---|---|
| Task accuracy (live-data golden set) | >= 0.95 | Shipped eval harness, weekly |
| Escalation precision | 1.0 (every must-escalate scenario escalated) | Mechanical scoring, harness + live approver feedback |
| Unsourced-figure incidents | 0 | Validator audit events |
| Approver satisfaction | Approvers confirm escalations were correct and decision-ready (figures attached) | Per-escalation feedback log |
| Bias parity (decision outcomes) | No decision-outcome disparities | Bias suite per promoted revision |
| Redaction efficacy | >= 92% on seeded-PII suite, no live PII leak incidents | Redaction suite + audit events |
| Reliability | No failed runs attributable to the chassis | Harness + OTel |
| Budget rail breaches | 0 tasks exceeding $0.50 / 60k tokens / 16 calls without graceful failure | Governance audit events |

Any threshold miss pauses expansion: the config snapshot makes rollback a repoint, not a redeploy, and the human gate in the improvement loop is the decision point for both promotion and rollback.

## Standing Commitments Across All 90 Days

- Promotion is never autonomous: every config change passes the human gate.
- Payments never execute: the $10,000 authority limit and escalation-only payment design hold in every phase.
- Every session is reconstructable: config snapshot, replayable checkpoints, OTel spans, retrievable at `GET /v1/audit/{session_id}`.
- G42 can independently re-benchmark at any time: the eval harness ships with the platform.
