"""Load test against a live deployment. Two profiles:

- gateway: /health and authenticated /v1/agents at 1/10/50 concurrent users
  (measures the chassis itself, no LLM variance)
- task: full agent task executions at lower concurrency (end-to-end, includes
  LLM latency; reported separately because the LLM dominates)

Reports sustained req/s, p50/p95 latency, error rate, and degradation
behavior (429 with Retry-After is graceful, 5xx is not).

Usage: .venv/bin/python -m stress.load_test [base_url]
"""
import asyncio
import json
import os
import statistics
import sys
import time

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
RESULTS = os.path.join(os.path.dirname(__file__), "results")


async def worker(client, url, method, payload, headers, duration, out):
    end = time.monotonic() + duration
    while time.monotonic() < end:
        t0 = time.perf_counter()
        try:
            if method == "GET":
                r = await client.get(url, headers=headers)
            else:
                r = await client.post(url, json=payload, headers=headers)
            out.append((time.perf_counter() - t0, r.status_code))
        except Exception:
            out.append((time.perf_counter() - t0, 599))


async def run_profile(name, url, method, payload, headers, concurrency, duration):
    out = []
    async with httpx.AsyncClient(timeout=180) as client:
        await asyncio.gather(*[
            worker(client, url, method, payload, headers, duration, out)
            for _ in range(concurrency)])
    lat = sorted(x[0] for x in out)
    codes = [x[1] for x in out]
    n = len(out)
    pct = lambda p: round(lat[min(n - 1, int(p / 100 * (n - 1)))] * 1000, 1) if n else 0
    return {
        "profile": name, "concurrency": concurrency, "duration_s": duration,
        "requests": n, "req_per_s": round(n / duration, 1),
        "latency_p50_ms": pct(50), "latency_p95_ms": pct(95),
        "ok_2xx": sum(1 for s in codes if s < 300),
        "rate_limited_429": codes.count(429),
        "server_errors_5xx": sum(1 for s in codes if 500 <= s < 600),
        "error_rate": round(sum(1 for s in codes if s >= 500) / n, 4) if n else 0,
    }


async def main():
    async with httpx.AsyncClient() as c:
        tok = (await c.post(f"{BASE}/v1/auth/token",
                            json={"api_key": "demo-analyst-key"})).json()["access_token"]
    auth = {"Authorization": f"Bearer {tok}"}
    rows = []
    for conc in (1, 10, 50):
        rows.append(await run_profile(f"gateway-health-c{conc}", f"{BASE}/health",
                                      "GET", None, None, conc, 10))
        print(rows[-1])
    # authenticated endpoint (JWT verify + RBAC on every request)
    rows.append(await run_profile("gateway-authed-c10", f"{BASE}/v1/agents",
                                  "GET", None, auth, 10, 10))
    print(rows[-1])
    # full agent tasks: 5 concurrent users for 60s (real LLM calls)
    rows.append(await run_profile("agent-task-c5", f"{BASE}/v1/agents/finance/tasks",
                                  "POST", {"task": "What is the AR aging summary?",
                                           "task_type": "aging_analysis"}, auth, 5, 60))
    print(rows[-1])
    report = {"base_url": BASE, "ts": time.time(), "profiles": rows}
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "load_test.json"), "w") as f:
        json.dump(report, f, indent=2)


if __name__ == "__main__":
    asyncio.run(main())
