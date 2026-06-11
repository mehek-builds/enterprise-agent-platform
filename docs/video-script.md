# "Watch the Agent Work" Video Scripts (2-3 min each)

You talk; Claude drives the screen (clicks, typing, tab switches) in sync
with your speech via the Granola transcript. Pause naturally while results
stream in; Claude clicks the next thing when your words reach the next beat.

## Video 1: Financial Intelligence Agent (~2:30)

### Beat 1, open (~25s)
SCREEN: landing page (Claude has it up)

"Hi, I'm Mehek Mandal. This is the G42 Intelligence Agent Platform, live at
this URL: one governed chassis built on LangGraph and FastAPI, serving three
enterprise agents from a single deployment. It comes out of my production
work: Nucleus, my agency's analytics pipeline behind client work for
Perplexity, Gamma, and Chess.com, and Traeco, my agent governance startup.
This is the Financial Intelligence Agent."

### Beat 2, live task (~40s)
CLAUDE CLICKS: "Run this task live" on the Finance card

"I'm asking it to explain the April variance for cost center CC-FIN, live,
real LLM calls over a synthetic ledger. The design rule: every figure must
trace to a tool output; a validator rejects unsourced numbers before any
answer is released. And there it is: 119 percent over budget, and it found
the real driver, duplicated postings in professional services. Read the
exact figures off the screen as they appear; they come from the ledger
tool, not the model's memory."

### Beat 3, forbidden action (~30s)
CLAUDE CLICKS: "Try a forbidden action"

"Now watch me try to make it pay a 45,000 dollar invoice with no approvals.
Status: escalated. It didn't just refuse in words; the refusal is a tool
call through an escalation gate, queued for a human approver with the
figures attached. Payments, hires, and contract awards can never execute
autonomously on this platform."

### Beat 4, audit trail (~30s)
CLAUDE CLICKS: "View audit trail"

"And here's what most agent demos can't show: the full audit trail of what
you just watched. A hash of the exact configuration it ran under, every LLM
call with token counts, every tool call, the escalation event. PII is
redacted by Microsoft Presidio before text ever reaches the model, and the
redactions are logged here too. Any decision is replayable, step by step."

### Beat 5, changelog (~20s)
CLAUDE SWITCHES TAB: /changelog

"G42 asks for version history showing lifecycle maturity. This platform
generates its own: every revision was promoted through an eval, shadow-eval,
human-approval loop, and the changelog records the benchmark delta that
justified it. Self-improving, never silently."

### Beat 6, close (~25s)
CLAUDE SWITCHES TAB: /dashboard

"Finally, impact telemetry: tasks automated, hours saved, cost per task,
escalation rates, computed from the same audit-grade data, so value-linked
compensation is measurable from day one. Benchmarks: task accuracy 1.0,
escalation precision 1.0, 135 of 135 runs without an error, and the full
eval harness ships with this submission so your team can reproduce every
number. Thanks for watching."

## Video 2: Human Capital Intelligence Agent

Same 6 beats. Swap:
- Beat 1 last line: "This is the Human Capital Intelligence Agent."
- Beat 2: shortlist for ROLE-ENG-01. Talking point: scores come only from
  structured qualifications. The dataset contains candidate clones,
  identical qualifications, different names and genders, and they score
  identically: 10 out of 10 bias-parity pairs.
- Beat 3: "make the offer to C-017 now" escalates; hiring is recommend-only.
- Beat 6 numbers: accuracy 0.92, the single miss was an over-escalation,
  the safe direction; escalation precision 1.0; 10/10 bias parity.

## Video 3: Strategic Sourcing Intelligence Agent

Same 6 beats. Swap:
- Beat 1 last line: "This is the Strategic Sourcing Intelligence Agent."
- Beat 2: 3-way match on PO-0015. Talking point: the match is deterministic
  code, not LLM arithmetic; it catches a duplicate invoice, 150,175 dollars
  billed twice, and across the dataset it catches exactly 12 seeded
  mismatches in 100 purchase orders with zero false positives.
- Beat 3: "award the cloud contract to S-014 now" escalates; awards always
  go to a human.
- Beat 6 numbers: accuracy 1.0, escalation precision 1.0, supplier scoring
  is performance-only with 6 of 6 country-pair parity.

## Sync protocol

1. Start a new Granola note, say "go" in chat, hit record in Loom.
2. Open each video with "starting video one/two/three" so Claude resets to
   the landing page and the right card.
3. Claude clicks each button as your speech reaches the beat, switches to
   changelog and dashboard at beats 5 and 6, and returns to the landing page
   after you say "thanks for watching."
