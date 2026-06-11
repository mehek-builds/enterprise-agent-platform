# Impact Telemetry: Human-Equivalent Time Assumptions

Value-linked compensation requires measurable enterprise impact. Every task
the platform completes records the task type, wall-clock completion time,
tokens, and cost. Hours saved are computed against the documented
human-equivalent assumptions below; each is a conservative estimate of the
time a trained analyst needs for the same deliverable, and each is a single
constant a G42 reviewer can adjust, with the rollup recomputing automatically.

## Financial Intelligence Agent

| Task type | Human-equivalent minutes | Basis |
|---|---|---|
| variance_analysis | 45 | pull BvA, reconcile to GL, identify drivers, write summary |
| aging_analysis | 30 | run aging, identify at-risk invoices, summarize buckets |
| cash_forecast | 40 | assemble daily positions, compute trend, write outlook |
| anomaly_review | 60 | scan entries, cross-check duplicates/exceptions, document |
| payment_processing | 15 | validate invoice, check authority, route for approval |
| reporting | 50 | assemble multi-source structured report |
| general | 20 | ad-hoc lookup and response |

## Human Capital Intelligence Agent

| Task type | Human-equivalent minutes | Basis |
|---|---|---|
| candidate_screening | 90 | review 15-20 profiles against criteria, score, shortlist |
| attrition_analysis | 60 | pull exits, segment, identify drivers, summarize |
| comp_review | 45 | band lookup, distribution check, out-of-band flags |
| org_modeling | 75 | scenario build, cost model, headcount deltas |
| lifecycle_check | 10 | HRIS status lookup |
| reporting | 50 | assemble multi-source structured report |
| general | 20 | ad-hoc lookup and response |

## Strategic Sourcing Intelligence Agent

| Task type | Human-equivalent minutes | Basis |
|---|---|---|
| supplier_evaluation | 60 | compile 24-month performance, score, write assessment |
| sourcing_decision | 90 | compare suppliers in category, rank, justify |
| contract_review | 120 | read contract, extract terms, flag risks |
| three_way_match | 30 | line-by-line PO/receipt/invoice reconciliation |
| requisition_intake | 20 | validate, categorize, budget check, route |
| reporting | 50 | assemble multi-source structured report |
| general | 20 | ad-hoc lookup and response |

## Computation

hours_saved = sum(human_equivalent_minutes) / 60 - sum(agent_completion_seconds) / 3600

Escalated tasks still accrue their human-equivalent time at the triage
fraction only (the agent assembled the figures and routed the decision; the
human approves rather than re-does the work). The current rollup counts
escalated tasks at full value, which overstates; the probationary deployment
calibrates this against observed approver time. Both the assumption and the
calibration plan are stated here so the compensation computation is
transparent from day one.
