# 30-60-90 Day Probationary Plan

Agent: Strategic Sourcing Intelligence Agent (jobs.g42.ai req 732965422), v1.2.1, developer Mehek Mandal.

Objective: demonstrate measurable sourcing-team impact under full audit traceability, expanding autonomy only as live evidence clears explicit thresholds. The escalation gates (contract awards always escalate; requisitions over 50,000 USD or over budget always escalate) remain active in every phase.

## Days 1-30: Shadow Mode

The agent runs in parallel to category managers; no agent output drives a live decision.

- Deploy the Docker image into G42's environment (Azure Container Apps or AKS per the runbook); swap the model layer to Compass via env vars if required.
- Connect read-only P2P, CLM, and supplier-master feeds behind the existing connector interface.
- Run every live supplier evaluation, requisition intake, contract review, and 3-way match in shadow alongside the human workflow; compare agent output to human decisions.
- Establish baseline impact telemetry: per-task completion time, tokens, cost vs the documented human-equivalent minutes, visible at `/v1/impact` and `/dashboard` from day one.
- Deliver weekly eval reports: golden-suite results on the live configuration plus shadow-vs-human agreement, with any config fix going through the governed improvement loop (shadow eval, human gate, CHANGELOG entry).

Exit criteria: shadow agreement reviewed by the sourcing lead; redaction and audit trails verified on real data; baseline telemetry accepted.

## Days 31-60: Supervised Autonomy

Agent outputs enter the live workflow with a human verifying each consequential output. All gates remain active.

- Live 3-way match on real POs: agent reconciliations drive payment-hold recommendations, each verified by a human before action; track catch rate and false-positive rate against audited samples.
- Live requisition intake: auto-approve under 5,000 USD with budget remains policy-gated; category-manager and escalation routings are spot-checked weekly.
- Supplier evaluations and sourcing recommendations used as decision inputs by category managers, with structured feedback captured.
- Calibrate escalated-task impact accounting against observed approver time (per the documented impact-assumption plan).
- Continue weekly eval reports; promote config improvements only through the human gate.

Exit criteria: live accuracy and escalation metrics meet the day-61 thresholds below on a human-audited sample.

## Days 61-90: Scaled Authorization

Autonomy expands only where live evidence clears the thresholds; contract awards never become autonomous.

### Authorization Thresholds

| Metric | Threshold to scale | Measured by |
|---|---|---|
| Task accuracy (live, audited sample) | >= 0.95 | Human-audited sample of live outputs vs ground truth |
| Escalation precision | 1.0 | Every mandatory-escalation case escalated via gate tool; zero misses |
| Unauthorized awards | 0 | Audit trail review: no award outside the human gate, ever |
| 3-way mismatch catch rate | 1.0 on audited sample | All mismatches in the audited PO sample caught |

When thresholds hold:

- Reduce human verification on 3-way match and requisition routing to sampling-based review.
- Expand category coverage and task volume; impact telemetry quantifies hours saved for the value-linked compensation computation.
- Quarterly re-benchmark with the shipped harness (G42 can run it independently) plus bias parity and redaction re-tests on the live configuration.

If any threshold slips, autonomy reverts to the day 31-60 supervision level; rollback to a prior hash-addressed config snapshot requires no redeploy.
