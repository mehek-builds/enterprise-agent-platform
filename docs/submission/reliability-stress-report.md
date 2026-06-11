# Reliability and Stress Test Report

Platform: G42 Intelligence Agent Platform v1.2.1, single container, single
uvicorn worker (the floor configuration; the chassis is stateless and scales
horizontally, the checkpointer volume is the only shared state). All tests
ran against the live deployment; the test sources ship in stress/ and are
re-runnable by G42.

## Load Test

| Profile | Concurrency | Sustained req/s | p50 | p95 | Server 5xx | Behavior under pressure |
|---|---|---|---|---|---|---|
| Gateway /health | 1 | 1,734 | 0.6 ms | 0.7 ms | 0 | nominal |
| Gateway /health | 10 | 1,902 | 3.6 ms | 15.1 ms | 0 | nominal |
| Gateway /health | 50 | 1,467 | 18.7 ms | 122.6 ms | 0 | latency degrades, zero errors |
| Authenticated endpoint | 10 | n/a (rate-limited) | 5.9 ms | 11.1 ms | 0 | graceful shedding: 429 + Retry-After |
| Full agent tasks (LLM end to end) | 5 users | 15 completed / 60 s | - | 4.4 s | 0 | within per-principal rate limits |

Zero server errors at every concurrency level; overload produces 429 with
Retry-After, never a crash. Reliability across the full benchmark campaign:
135/135 agent task executions (3 agents x 15 scenarios x 3 runs) completed
without an unhandled error.

## Adversarial Input Suite

10/10 attack classes defended (stress/results/adversarial.json):

| Attack class | Cases | Result |
|---|---|---|
| Auth bypass (no token, forged JWT) | 2 | rejected 401 |
| Malformed input (200KB payload, broken JSON) | 2 | rejected 422 |
| Routing abuse (unknown agent domain) | 1 | rejected 404 |
| Prompt injection (direct leak-and-pay, document-embedded award override) | 2 | no leak, no payment, no award; gates held |
| RBAC violation (viewer invoking restricted tools by name) | 1 | restricted tools never exposed or executed |
| Social engineering (record-alteration request) | 1 | escalated as policy violation |
| Load abuse (request burst) | 1 | 429 shedding, zero 5xx |

## Sustained Run

Heartbeat loop (stress/sustained_run.py): /health, authenticated call, and a
rotating real agent task on a 5-minute cycle, run overnight before
submission. Summary inserted at send time:

```
<SUSTAINED_RUN_SUMMARY>
```

## Degradation and Recovery Design

- Stateless chassis: restart loses nothing; sessions, audit trail, and
  checkpoints persist in the data volume
- Budget rails bound the worst case of any single task ($0.50, 60k tokens,
  16 LLM calls)
- Tool failures surface as structured errors to the model, which retries or
  escalates; they never crash a run
- Rollback is config repointing (see deployment runbook), zero redeploy
