"""Scenario-based performance benchmark harness.

Methodology (adapted from the Dial eval harness):
- Oracle answers are precomputed from the synthetic datasets and verified by
  assertion scripts, so the judge compares against ground truth, not vibes.
- LLM-as-judge with anti-bias controls: judge never sees agent metadata, low
  temperature, and any FAIL verdict is re-judged once (self-consistency);
  a task only fails on two independent FAIL verdicts.
- Escalation tasks are scored mechanically (status == escalated), no judge.
- Every task runs N times; latency/cost/reliability come from all runs.

Usage: .venv/bin/python -m evals.harness <domain> [runs_per_task]
"""
import json
import os
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from app import audit
from app.agent import AgentRunner
from app.llm import LLMClient
from app.packs.base import load_pack

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
JUDGE_PROMPT = """You are a strict evaluation judge. Compare the agent's answer to the oracle (ground truth) for this task.

SCENARIO: {scenario}
TASK GIVEN TO AGENT: {prompt}
ORACLE (ground truth): {oracle}
PASS CRITERIA: {pass_criteria}

AGENT ANSWER:
{answer}

The answer PASSES if it satisfies the pass criteria and its material facts and figures agree with the oracle (formatting and rounding to the nearest unit may differ; extra correct detail is fine; wrong or missing key figures fail).
Reply with exactly one line: PASS or FAIL, then a colon and a one-sentence reason."""


def judge(task: dict, answer: str, judge_llm: LLMClient) -> tuple[bool, str]:
    msg = JUDGE_PROMPT.format(answer=answer or "(no answer)", **{
        k: task.get(k, "") for k in ("scenario", "prompt", "oracle", "pass_criteria")})
    out = judge_llm.chat([{"role": "user", "content": msg}])
    text = (out["content"] or "").strip()
    verdict = text.upper().startswith("PASS")
    if not verdict:
        out2 = judge_llm.chat([{"role": "user", "content": msg}])
        text2 = (out2["content"] or "").strip()
        if text2.upper().startswith("PASS"):
            return True, "pass on self-consistency re-judge: " + text2
    return verdict, text


def run_one(runner: AgentRunner, task: dict) -> dict:
    t0 = time.perf_counter()
    try:
        out = runner.run_task(task["prompt"], task["task_type"])
        ok = True
    except Exception as e:
        out = {"status": "failed", "answer": None, "metrics": {}, "error": str(e)}
        ok = False
    return {"task_id": task["id"], "result": out, "no_unhandled_error": ok,
            "wall_seconds": time.perf_counter() - t0}


def run_suite(domain: str, runs_per_task: int = 3, workers: int = 6) -> dict:
    pack = load_pack(domain)
    audit.init_db()
    runner = AgentRunner(pack, "analyst")
    judge_llm = LLMClient()
    with open(os.path.join(pack.path, "golden_tasks.json")) as f:
        tasks = json.load(f)

    jobs = [(t, i) for t in tasks for i in range(runs_per_task)]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        runs = list(ex.map(lambda ti: {**run_one(runner, ti[0]), "run_idx": ti[1]}, jobs))

    # --- judge accuracy on non-escalation tasks (first run of each) ---------
    per_task = {}
    for t in tasks:
        t_runs = [r for r in runs if r["task_id"] == t["id"]]
        first = t_runs[0]["result"]
        if t.get("must_escalate"):
            passed = first.get("status") == "escalated"
            reason = f"status={first.get('status')}"
        else:
            passed, reason = judge(t, first.get("answer") or "", judge_llm)
            # an escalation on a routine task is a (safe) miss, not a pass
            if first.get("status") != "completed":
                passed, reason = False, f"status={first.get('status')}: {reason}"
        per_task[t["id"]] = {"passed": passed, "reason": reason,
                             "must_escalate": bool(t.get("must_escalate"))}

    # --- aggregate metrics ---------------------------------------------------
    latencies = sorted(r["result"].get("metrics", {}).get("latency_seconds", r["wall_seconds"])
                       for r in runs)
    costs = [r["result"].get("metrics", {}).get("cost_usd", 0) for r in runs]
    esc_tasks = [tid for tid, v in per_task.items() if v["must_escalate"]]
    esc_passed = sum(per_task[tid]["passed"] for tid in esc_tasks)
    acc_tasks = [tid for tid, v in per_task.items() if not v["must_escalate"]]

    def pct(sorted_vals, p):
        if not sorted_vals:
            return 0
        return sorted_vals[min(len(sorted_vals) - 1, int(round(p / 100 * (len(sorted_vals) - 1))))]

    report = {
        "domain": domain,
        "model": runner.llm.cfg.model,
        "runs_per_task": runs_per_task,
        "n_tasks": len(tasks),
        "n_runs": len(runs),
        "metrics": {
            "task_accuracy": round(sum(per_task[t]["passed"] for t in acc_tasks) / len(acc_tasks), 3),
            "escalation_precision": round(esc_passed / len(esc_tasks), 3) if esc_tasks else None,
            "latency_p50_s": round(pct(latencies, 50), 2),
            "latency_p95_s": round(pct(latencies, 95), 2),
            "reliability": round(sum(r["no_unhandled_error"] for r in runs) / len(runs), 3),
            "cost_per_task_usd": round(statistics.mean(costs), 5) if costs else 0,
            "total_cost_usd": round(sum(costs), 4),
        },
        "per_task": per_task,
        "ts": time.time(),
    }
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, f"{domain}.json"), "w") as f:
        json.dump(report, f, indent=2)
    return report


if __name__ == "__main__":
    domain = sys.argv[1]
    runs = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    rep = run_suite(domain, runs)
    print(json.dumps({k: v for k, v in rep.items() if k != "per_task"}, indent=2))
    for tid, v in rep["per_task"].items():
        print(("PASS " if v["passed"] else "FAIL "), tid, "-", v["reason"][:140])
