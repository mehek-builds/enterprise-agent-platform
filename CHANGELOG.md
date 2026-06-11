# Changelog

All notable configuration and capability revisions. Every entry pairs the
change with the benchmark evidence that justified it (the governed
improvement loop: eval, diagnose, propose, shadow eval, human gate, promote).

## [1.2.1] - 2026-06-11

Promoted after full-suite shadow eval. Finance: accuracy 12/12 held,
escalation precision 2/3 to 3/3. Adversarial defense 8/10 to 10/10.

### Changed
- Chassis: escalated runs now compose the final answer from the agent's last
  assembled figures plus the escalation reason, instead of the raw gate
  message. Diagnosis: correct escalations scored as failures because the
  figures were dropped (src-10).
- Prompts: payment/award refusals must produce the gate tool call, not a
  text refusal (fin-14, src-15); compliance failures are disqualifying in
  supplier assessments (src-03); analysis is not a decision and must not
  over-escalate (hc-12).
- RBAC: viewer role loses raw query access (reporting-only by definition)
  and gains the `escalate` safety valve; rate limiting extended to all
  authenticated endpoints (adversarial cases 8 and 10).
- Bias parity judge scores decision outcomes (flag/clear, escalate/not,
  scores) rather than rationale wording; methodology documented.

## [1.2.0] - 2026-06-11

Promoted after shadow eval against the finance golden suite (15 scenarios).
Accuracy 8/12 to 12/12 on non-escalation tasks; escalation precision 2/3 to 3/3.

### Changed
- `analyze_variance` now surfaces `control_exceptions` (duplicate postings,
  weekend postings >= 25k, round-number outliers) ahead of `largest_entries`.
  Diagnosis: agent attributed variances to the largest entries instead of the
  underlying control exceptions (failing scenarios fin-01, fin-02, fin-03).
- `cash_position` defaults to the latest available day and returns a 7-day
  trend block. Diagnosis: "current cash position" requests looped on a
  required-date error until the budget rail fired (fin-08, fin-09).
- Finance system prompt rules 5-7: cite record IDs, lead variance stories
  with control exceptions, and route record-alteration requests through the
  `escalate` tool instead of refusing in prose (fin-15 completed without
  escalating).
- Redaction layer: domain false-positive filters (currency-shaped
  PHONE_NUMBER spans, single-token PERSON spans, sub-0.35 confidence).
  Diagnosis: output redaction replaced "$176,169.73" with <PHONE_NUMBER> and
  "Variance" with <PERSON>; seeded-PII efficacy held at 92% after the filters.

## [1.1.0] - 2026-06-11

### Added
- Three domain packs on the shared chassis: finance, human_capital, sourcing
  (8 tools each, seeded deterministic datasets, 15 golden scenarios each,
  bias parity suites: 6 finance pairs, 10 human capital, 6 sourcing).
- Scenario-based benchmark harness with oracle-anchored LLM judge
  (self-consistency re-judge on FAIL) and escalation scored mechanically.
- Bias parity harness and seeded-PII redaction efficacy test.

## [1.0.0] - 2026-06-11

### Added
- Shared agent chassis: FastAPI gateway (JWT auth, RBAC roles, rate limiting),
  LangGraph core with SQLite checkpointer, validator node with bounded
  self-correction, escalation gates, budget rails.
- Governance wrapper: config snapshot at session start (hash-addressed),
  Presidio PII redaction on input and output, OTel spans, per-role tool
  allowlists enforced at the graph layer.
- Impact telemetry: per-task type/time/tokens/cost vs documented
  human-equivalent assumptions, rollup endpoint for value-linked compensation.
- Model layer: OpenAI-compatible client, swappable to G42 Compass/JAIS via
  LLM_BASE_URL and LLM_MODEL env vars.

### Lineage
- Architecture descends from Nucleus (2025, Elemental Growth production
  analytics pipeline) and the Dial eval harness (2026): connector interface,
  config-observability pattern, oracle-anchored judging.
