# 30-60-90 Day Probationary Plan

Human Capital Intelligence Agent, version 1.2.1. The plan moves from shadow mode to supervised autonomy to scaled authorization, with every gate measured by the same shipped harness that produced the submitted benchmarks, plus live-data parity monitoring. Fairness evidence gates every autonomy increase.

## Days 1-30: Shadow Mode

The agent runs in parallel to recruiters and HR analysts. Humans remain the system of record for every output; the agent's work is compared, not consumed.

| Activity | Detail |
|---|---|
| Parallel screening | Agent produces shortlists alongside recruiter screening on live candidate flow; outputs compared, never sent to candidates or hiring managers as decisions |
| Parity monitoring on live data | The bias parity methodology (matched-pair, decision-outcome judging) runs against live candidate flow, not just the synthetic suite; any disparity is a stop-and-diagnose event |
| Parallel analytics | Attrition, comp review, org modeling, and reporting outputs compared against analyst-produced equivalents |
| Telemetry baselines | `/v1/impact` accumulates per-task time, tokens, and cost; human-equivalent assumptions (docs/impact-assumptions.md) calibrated against observed analyst time |
| Connector integration | HRIS (Workday or SAP SuccessFactors) and ATS read connectors wired behind the existing provider interface; golden suite re-run against live-shaped data |
| Audit verification | G42 reviewers pull session trails via `/v1/audit/{session_id}` to confirm replayability and config snapshot integrity |

Exit criteria: golden suite green on live connectors, zero parity violations in shadow, telemetry baselines established.

## Days 31-60: Supervised Autonomy

Agent outputs are consumed (shortlists, analyses, reports go to their audiences) with every decision still gated by a human, which is the agent's permanent design anyway.

| Activity | Detail |
|---|---|
| Live screening shortlists | Recruiters work from agent shortlists; every hire decision flows through `approve_hire` to the hiring manager and HR business partner |
| Escalation gates active | All compensation changes, offers, and policy-violation requests escalate; escalation volume and precision tracked weekly |
| Weekly parity and accuracy reports | Produced by the shipped harness against the live week's traffic: task accuracy, escalation precision, identity-pair parity, redaction efficacy |
| Improvement loop in production | Any failing case enters the governed loop (eval, diagnose, propose, shadow eval, human gate, promote); promotions documented in the CHANGELOG with benchmark deltas, as 1.2.0 and 1.2.1 were |
| Impact reporting | `/dashboard` rollup reviewed with the business owner; value-linked compensation computation validated against calibrated assumptions |

Exit criteria: sustained weekly metrics at or above the day 61-90 thresholds for the final two consecutive weeks.

## Days 61-90: Scaled Authorization

Scope expands (more roles, more departments, higher shortlist volume) only as thresholds are sustained on live data. Decisions remain human-gated permanently; what scales is analytical autonomy and volume, never decision authority.

### Authorization thresholds

| Metric | Threshold to scale | Measured by |
|---|---|---|
| Task accuracy (non-escalation) | >= 0.95 sustained | Weekly harness run against live traffic |
| Escalation precision | 1.00 | Mechanical scoring of must-escalate cases |
| Identity-pair parity | 1.00 sustained on live data | Matched-pair parity suite on live candidate flow |
| Policy-violation compliance | Zero noncompliance: every protected-attribute filtering request refused and escalated | Audit trail review of escalation events |
| Redaction efficacy | No regression below the 92% baseline | Seeded-PII test per promoted revision |
| Reliability | 1.00 task completion | Gateway and OTel telemetry |

Any threshold breach pauses scaling and routes through the improvement loop; rollback to the prior config snapshot is immediate and requires no redeploy. The same 30-60-90 evidence stream feeds the value-linked compensation computation: time saved per task type, measured from the agent's own audit-grade telemetry, calibrated during days 1-30, validated during days 31-60, and contractually referenceable from day 61.
