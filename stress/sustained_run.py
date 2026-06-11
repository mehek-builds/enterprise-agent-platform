"""Sustained-run heartbeat: exercises the live deployment on an interval and
records uptime evidence. Run overnight before submission.

Every cycle: /health check, one lightweight authenticated call, and every
6th cycle one real agent task (rotating domain). Appends one JSON line per
cycle to stress/results/sustained_run.jsonl; summarize with --report.

Usage:
  .venv/bin/python -m stress.sustained_run [base_url] [interval_seconds]
  .venv/bin/python -m stress.sustained_run --report
"""
import json
import os
import sys
import time

import httpx

OUT = os.path.join(os.path.dirname(__file__), "results", "sustained_run.jsonl")
TASKS = [
    ("finance", "What is the current AR aging summary?", "aging_analysis"),
    ("human_capital", "What is the 12-month attrition rate and top driver?", "attrition_analysis"),
    ("sourcing", "Evaluate supplier S-001 and give the composite score.", "supplier_evaluation"),
]


def report():
    rows = [json.loads(l) for l in open(OUT)]
    ok = [r for r in rows if r["health_ok"]]
    tasks = [r for r in rows if r.get("task_status")]
    t0, t1 = rows[0]["ts"], rows[-1]["ts"]
    print(json.dumps({
        "window_hours": round((t1 - t0) / 3600, 2),
        "heartbeats": len(rows),
        "health_ok": len(ok),
        "uptime_pct": round(100 * len(ok) / len(rows), 2),
        "agent_tasks_run": len(tasks),
        "agent_tasks_completed": sum(1 for r in tasks if r["task_status"] in ("completed", "escalated")),
        "max_observed_uptime_s": max(r.get("server_uptime_s", 0) for r in rows),
    }, indent=2))


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8042"
    interval = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    cycle = 0
    while True:
        row = {"ts": time.time(), "health_ok": False}
        try:
            with httpx.Client(timeout=120) as c:
                h = c.get(f"{base}/health").json()
                row["health_ok"] = h["status"] == "ok"
                row["server_uptime_s"] = h["uptime_seconds"]
                tok = c.post(f"{base}/v1/auth/token",
                             json={"api_key": "demo-analyst-key"}).json()["access_token"]
                auth = {"Authorization": f"Bearer {tok}"}
                row["authed_ok"] = c.get(f"{base}/v1/agents", headers=auth).status_code == 200
                if cycle % 6 == 0:
                    d, task, tt = TASKS[(cycle // 6) % len(TASKS)]
                    r = c.post(f"{base}/v1/agents/{d}/tasks", headers=auth,
                               json={"task": task, "task_type": tt}).json()
                    row["task_domain"] = d
                    row["task_status"] = r.get("status")
        except Exception as e:
            row["error"] = str(e)[:200]
        with open(OUT, "a") as f:
            f.write(json.dumps(row) + "\n")
        cycle += 1
        time.sleep(interval)


if __name__ == "__main__":
    if "--report" in sys.argv:
        report()
    else:
        main()
