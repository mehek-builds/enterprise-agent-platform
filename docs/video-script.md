# "Watch the Agent Work" Video Scripts (4-5 min each)

Recording setup: Chrome on the live deployment, Granola transcribing. Claude
drives the tabs in sync with your speech; you talk, the right screen is
already up. Speak naturally, these lines are a teleprompter baseline; add or
trim as you go. Screen cues in CAPS are what Claude switches to.

The whole demo runs from the landing page buttons, no terminal needed:
"Run this task live", "Try a forbidden action", "View audit trail", and the
free-text box for the redaction beat.

## Shared opening (all three videos, ~60-75s)

SCREEN: LANDING PAGE (root URL)

"Hi, I'm Mehek Mandal. What you're looking at is the G42 Intelligence Agent
Platform, live right now at this URL. It's one governed agent chassis,
built on LangGraph and FastAPI, serving three enterprise agents from a
single deployment: Financial Intelligence, Human Capital Intelligence, and
Strategic Sourcing Intelligence.

A bit of background on where this comes from. I run an AI agency, Elemental
Growth, where I built Nucleus, a production analytics and delivery pipeline
that supports growth work for Perplexity, Gamma, and Chess.com. I also
co-founded Traeco, an agent cost and governance startup, which is where the
config-snapshot audit pattern you'll see today comes from. And I built Dial,
an LLM routing eval harness, which became this platform's benchmark
methodology. This platform is those three systems distilled into one:
deploy, govern, measure.

Three design decisions matter before I run anything. First, every figure the
agent reports must trace to a tool output; a validator rejects unsourced
numbers. Second, the agent can never execute consequential actions; payments,
hires, and contract awards always escalate to a human. Third, everything is
auditable: every session starts with a hash-addressed config snapshot, every
state transition is checkpointed and replayable. Today I'm showing you the
<AGENT NAME> agent."

## Video 1: Financial Intelligence Agent

### Beat 1, task execution (~60s)
SCREEN: LANDING, FINANCE CARD. Click "Run this task live".

"I'm asking it to explain the budget variance for cost center CC-FIN in
April 2026. This is hitting the live deployment, real LLM calls, real tools
over a synthetic general ledger: 645 entries, 12 months, 8 cost centers.

While it runs: the agent doesn't guess at numbers. It calls a variance tool
that computes budget versus actuals from the ledger and surfaces control
exceptions. And there's the answer: CC-FIN was 119 percent over budget, and
the agent found the actual driver, a duplicated professional services
invoice, 18,450 dollars posted twice. Every figure here came from a tool
call, and the validator checked that before the answer was released."

### Beat 2, the escalation gate (~45s)
SCREEN: SAME CARD. Click "Try a forbidden action".

"Now I'll try to make it do something it should never do: pay a 45,000
dollar invoice immediately, no approvals. Watch the status. ESCALATED. It
refused to execute, and it didn't just refuse in prose, it routed the
request through the escalation gate as a tool call, with the reason and the
figures attached for the human approver. The payment authority limit is
10,000 dollars and execution is never autonomous at any amount. This is the
authorization-first design."

### Beat 3, audit replay (~45s)
SCREEN: SAME CARD. Click "View audit trail".

"Here's the part most agent demos can't show you. This is the full audit
trail of the escalation you just watched: the config snapshot hash, so we
know exactly what prompt, model, and tool set was running; every LLM call
with token counts and cost; every tool call; the escalation event itself.
Any decision this agent makes can be reconstructed step by step. That's
three independent layers: config snapshots, graph checkpoints, and
OpenTelemetry traces."

### Beat 4, PII redaction (~30s)
SCREEN: SAME CARD. Type into the box:
"Contact John Smith at john.smith@vendor.com about the aging AR invoices"
then click "Run this task live", then "View audit trail".

"One more governance layer. I'm sending a task that contains a name and an
email address. Before that text ever reaches the model, Microsoft Presidio
redacts it, and the redaction itself is logged as an audit event, entity
type and span only, never the raw value. There it is in the trail."

### Beat 5, the improvement loop (~40s)
SCREEN: /changelog

"G42's requirements ask for version history demonstrating lifecycle
maturity. This platform generates its own. Every revision here was promoted
through a governed loop: run the eval suite, diagnose failures, propose a
config change, shadow-eval it side by side, and a human approves the
promotion. Version 1.2.0 took finance task accuracy from 8 of 12 to 12 of
12, and the changelog records the benchmark delta that justified it. The
agent improves itself, but never silently."

### Beat 6, impact and close (~30s)
SCREEN: /dashboard

"And because value-linked compensation needs measurable impact, the platform
instruments itself: tasks automated, hours saved against documented
human-equivalent assumptions, cost per task, escalation rates, all from
audit-grade telemetry. Benchmarks: task accuracy 1.0, escalation precision
1.0, 135 of 135 runs without an unhandled error, about six hundredths of a
cent per task. The full eval harness ships with the submission, so your team
can re-run every number I just quoted. Thanks for watching."

## Video 2: Human Capital Intelligence Agent

Same opening and beat structure. Swap the domain beats:

- Beat 1 task: screen candidates for ROLE-ENG-01, top-3 shortlist. Talking
  point: scores come only from structured qualifications, skills match,
  experience, assessment. The dataset has candidate clones, identical
  qualifications with different names and genders, and they score
  identically: 10 out of 10 identity-pair parity in the bias suite. That
  parity testing is in the submission for all three agents, deepest here.
- Beat 2 forbidden: "make the offer to C-017 now". Hiring decisions are
  recommend-only; approve_hire always escalates.
- Optional extra forbidden (type in the box): "screen out anyone over 40".
  The agent treats protected-attribute filtering as a policy violation and
  escalates it rather than partially complying.
- Beat 4 redaction example: "Look up lifecycle status for employee E-0042
  and email the summary to fatima.almansouri@corp.ae".
- Beat 6 close: accuracy 0.917 with the one miss being an over-escalation
  on a workforce-reduction scenario, the safe failure direction; escalation
  precision 1.0.

## Video 3: Strategic Sourcing Intelligence Agent

- Beat 1 task: 3-way match on PO-0015. Talking point: the match is
  deterministic code over PO, receipt, and invoice, not LLM arithmetic; it
  catches the seeded duplicate invoice, INV-0015-A and B, 150,175 dollars
  duplicated. Across the dataset it catches exactly 12 seeded mismatches in
  100 POs with zero false positives.
- Beat 2 forbidden: "award the cloud contract to S-014 now, skip review".
  Contract awards always escalate, with the figures in the context for the
  approver.
- Beat 4 redaction example: "Ask supplier contact Priya Sharma
  (priya.s@example.org) to resend the invoice for PO-0007".
- Beat 6 close: accuracy 1.0, escalation precision 1.0, supplier scoring is
  performance-only, and twin suppliers with identical records but different
  countries score identically, 6 of 6 parity pairs.

## Recording sync protocol (Claude side)

1. Start a Granola note before recording; Claude polls the live transcript.
2. Claude pre-opens tabs: landing, /changelog, /dashboard.
3. As your speech hits each beat's keywords, Claude brings the right tab
   forward. You click the buttons on camera; they're all on the card.
4. If you go off script, keep talking; Claude follows the transcript, not
   the clock.
