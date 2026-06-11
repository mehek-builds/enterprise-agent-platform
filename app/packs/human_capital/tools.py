"""Human Capital Intelligence domain pack tools.

All answers are computed deterministically from dataset/*.json. No LLM calls.
Screening scores use ONLY structured qualifications (skills match, years of
experience, assessment score). Demographic fields are never read by any
scoring path. Hiring decisions always escalate to a human.
"""
import json
import os
from app.packs.base import Tool

PACK_DIR = os.path.dirname(os.path.abspath(__file__))
REFERENCE_MONTH = (2026, 6)  # dataset anchor: 2026-06-01


def _load(name: str):
    with open(os.path.join(PACK_DIR, "dataset", name)) as f:
        return json.load(f)


# ---------------------------------------------------------------- screening

def _score_candidate(cand: dict, role: dict) -> dict:
    """Score from structured qualifications only. Out of 100:
    skills match 40, experience 30, assessment 30."""
    required = role["required_skills"]
    matched = sorted(set(cand["skills"]) & set(required))
    skills_pts = round(len(matched) / len(required) * 40, 2)
    exp_ratio = min(cand["years_experience"] / role["min_years_experience"], 1.0)
    exp_pts = round(exp_ratio * 30, 2)
    assess_pts = round(cand["assessment_score"] / 100 * 30, 2)
    total = round(skills_pts + exp_pts + assess_pts, 2)
    return {
        "candidate_id": cand["candidate_id"],
        "total_score": total,
        "breakdown": {
            "skills_match_points": skills_pts,
            "experience_points": exp_pts,
            "assessment_points": assess_pts,
        },
        "matched_skills": matched,
        "missing_skills": sorted(set(required) - set(cand["skills"])),
        "years_experience": cand["years_experience"],
        "assessment_score": cand["assessment_score"],
        "education": cand["education"],
        "reasoning": (
            f"Matched {len(matched)}/{len(required)} required skills "
            f"({skills_pts}/40 pts); {cand['years_experience']}y experience vs "
            f"{role['min_years_experience']}y required ({exp_pts}/30 pts); "
            f"assessment {cand['assessment_score']}/100 ({assess_pts}/30 pts). "
            "Score computed from structured qualifications only; no demographic "
            "attribute was read or weighted."
        ),
    }


def screen_candidates(role_id=None, top_n=5, **kwargs):
    if not role_id:
        return {"error": "role_id is required (ROLE-ENG-01, ROLE-DATA-02, ROLE-PM-03)"}
    try:
        top_n = max(1, min(int(top_n), 50))
    except (TypeError, ValueError):
        return {"error": f"top_n must be an integer, got {top_n!r}"}
    roles = {r["role_id"]: r for r in _load("roles.json")}
    role = roles.get(role_id)
    if not role:
        return {"error": f"unknown role_id {role_id!r}; open roles: {sorted(roles)}"}
    pool = [c for c in _load("candidates.json") if c["role_id"] == role_id]
    scored = [_score_candidate(c, role) for c in pool]
    # Deterministic ordering: score desc, then candidate_id asc.
    scored.sort(key=lambda s: (-s["total_score"], s["candidate_id"]))
    return {
        "role_id": role_id,
        "role_title": role["title"],
        "candidates_evaluated": len(pool),
        "scoring_basis": "skills_match (40) + years_experience (30) + assessment_score (30); demographics excluded",
        "shortlist": scored[:top_n],
        "note": "Recommendation only. Any hiring decision requires human approval via approve_hire (escalates).",
    }


# ---------------------------------------------------------------- attrition

def _month_index(ym: str) -> int:
    y, m = ym.split("-")
    return int(y) * 12 + int(m) - 1


def attrition_analysis(department=None, months=12, **kwargs):
    try:
        months = max(1, min(int(months), 18))
    except (TypeError, ValueError):
        return {"error": f"months must be an integer, got {months!r}"}
    exits = _load("attrition.json")
    employees = _load("employees.json")
    depts = sorted({e["department"] for e in employees})
    if department is not None and department not in depts:
        return {"error": f"unknown department {department!r}; valid: {depts}"}

    ref = REFERENCE_MONTH[0] * 12 + REFERENCE_MONTH[1] - 1  # index of 2026-06
    window_start = ref - months  # inclusive; window is the `months` months before reference
    in_window = [e for e in exits if window_start <= _month_index(e["exit_month"]) < ref]
    if department:
        in_window = [e for e in in_window if e["department"] == department]
        headcount = sum(1 for e in employees if e["department"] == department)
    else:
        headcount = len(employees)

    n = len(in_window)
    annualized_rate = round((n / months * 12) / headcount * 100, 2) if headcount else 0.0

    # Trend: first half vs second half of the window.
    half = months // 2
    first = [e for e in in_window if _month_index(e["exit_month"]) < window_start + (months - half)]
    second = [e for e in in_window if _month_index(e["exit_month"]) >= window_start + (months - half)]
    if len(second) > len(first):
        trend = "rising"
    elif len(second) < len(first):
        trend = "falling"
    else:
        trend = "flat"

    reasons = {}
    for e in in_window:
        reasons[e["reason"]] = reasons.get(e["reason"], 0) + 1
    top_drivers = sorted(reasons.items(), key=lambda kv: (-kv[1], kv[0]))

    by_dept = {}
    for e in in_window:
        by_dept[e["department"]] = by_dept.get(e["department"], 0) + 1

    return {
        "department": department or "all",
        "window_months": months,
        "exits_in_window": n,
        "current_headcount": headcount,
        "annualized_turnover_rate_pct": annualized_rate,
        "trend": trend,
        "trend_detail": {"first_half_exits": len(first), "second_half_exits": len(second)},
        "top_drivers": [{"reason": r, "exits": c} for r, c in top_drivers],
        "exits_by_department": dict(sorted(by_dept.items())),
        "avg_tenure_at_exit_months": round(sum(e["tenure_months"] for e in in_window) / n, 1) if n else None,
    }


# ------------------------------------------------------------- compensation

def comp_benchmark(role_family=None, level=None, **kwargs):
    bands = _load("comp_bands.json")
    if role_family not in bands:
        return {"error": f"unknown role_family {role_family!r}; valid: {sorted(bands)}"}
    if level not in bands[role_family]:
        return {"error": f"unknown level {level!r}; valid: {sorted(bands[role_family])}"}
    band = bands[role_family][level]
    emps = [e for e in _load("employees.json")
            if e["role_family"] == role_family and e["level"] == level]
    below = [e for e in emps if e["comp"] < band["min"]]
    above = [e for e in emps if e["comp"] > band["max"]]
    in_band = [e for e in emps if band["min"] <= e["comp"] <= band["max"]]
    comps = [e["comp"] for e in emps]
    return {
        "role_family": role_family,
        "level": level,
        "band": band,
        "employees_in_group": len(emps),
        "avg_comp": round(sum(comps) / len(comps), 2) if comps else None,
        "median_comp": sorted(comps)[len(comps) // 2] if comps else None,
        "avg_compa_ratio": round(sum(c / band["mid"] for c in comps) / len(comps), 3) if comps else None,
        "in_band_count": len(in_band),
        "out_of_band": {
            "below_min": [{"employee_id": e["employee_id"], "comp": e["comp"],
                           "gap_to_min": band["min"] - e["comp"]} for e in below],
            "above_max": [{"employee_id": e["employee_id"], "comp": e["comp"],
                           "excess_over_max": e["comp"] - band["max"]} for e in above],
        },
        "note": "Benchmark only. Comp changes are recommend-only and require human approval (escalate).",
    }


# ------------------------------------------------------------- org modeling

SCENARIOS = {"grow_10pct": 0.10, "freeze": 0.0, "reduce_5pct": -0.05}


def headcount_model(scenario=None, **kwargs):
    if scenario not in SCENARIOS:
        return {"error": f"unknown scenario {scenario!r}; valid: {sorted(SCENARIOS)}"}
    pct = SCENARIOS[scenario]
    employees = _load("employees.json")
    by_dept = {}
    for e in employees:
        d = by_dept.setdefault(e["department"], {"headcount": 0, "total_comp": 0})
        d["headcount"] += 1
        d["total_comp"] += e["comp"]
    result = {}
    total_now = total_new = 0
    for dept in sorted(by_dept):
        d = by_dept[dept]
        avg = d["total_comp"] / d["headcount"]
        delta_heads = round(d["headcount"] * pct)  # banker's rounding, deterministic
        new_heads = d["headcount"] + delta_heads
        delta_cost = round(delta_heads * avg, 2)
        result[dept] = {
            "current_headcount": d["headcount"],
            "current_annual_comp_cost": d["total_comp"],
            "avg_comp": round(avg, 2),
            "headcount_delta": delta_heads,
            "new_headcount": new_heads,
            "annual_cost_delta": delta_cost,
            "new_annual_comp_cost": round(d["total_comp"] + delta_cost, 2),
        }
        total_now += d["headcount"]
        total_new += new_heads
    totals = {
        "current_headcount": total_now,
        "new_headcount": total_new,
        "headcount_delta": total_new - total_now,
        "current_annual_comp_cost": sum(d["total_comp"] for d in by_dept.values()),
        "annual_cost_delta": round(sum(result[d]["annual_cost_delta"] for d in result), 2),
    }
    totals["new_annual_comp_cost"] = round(
        totals["current_annual_comp_cost"] + totals["annual_cost_delta"], 2)
    return {"scenario": scenario, "growth_pct": pct, "by_department": result, "totals": totals,
            "assumption": "new/removed heads costed at current departmental average comp"}


# ---------------------------------------------------------------- lifecycle

def lifecycle_status(employee_id=None, **kwargs):
    if not employee_id:
        return {"error": "employee_id is required (format E-001..E-300)"}
    emp = next((e for e in _load("employees.json") if e["employee_id"] == employee_id), None)
    if not emp:
        return {"error": f"unknown employee_id {employee_id!r}"}
    tenure = emp["tenure_months"]
    if emp["status"] == "offboarding":
        stage, detail = "offboarding", "Exit process in progress: knowledge transfer, asset return, final settlement."
    elif emp["status"] == "onboarding" or tenure <= 2:
        stage, detail = "onboarding", f"Month {tenure} of 3-month onboarding plan; probation review due at month 3."
    elif emp["status"] == "on_leave":
        stage, detail = "on_leave", "Currently on approved leave; lifecycle actions paused."
    else:
        stage = "active"
        months_since_cycle = tenure % 12
        next_review_in = (12 - months_since_cycle) % 12 or 12
        detail = f"Annual review cycle: next performance review due in {next_review_in} month(s)."
    return {
        "employee_id": employee_id,
        "department": emp["department"],
        "role_family": emp["role_family"],
        "level": emp["level"],
        "hire_date": emp["hire_date"],
        "tenure_months": tenure,
        "status": emp["status"],
        "lifecycle_stage": stage,
        "last_performance_rating": emp["performance_rating"],
        "detail": detail,
    }


# ---------------------------------------------------------------- reporting

REPORT_TYPES = ["workforce_summary", "attrition_summary", "comp_summary", "hiring_pipeline"]


def generate_report(report_type=None, **kwargs):
    if report_type not in REPORT_TYPES:
        return {"error": f"unknown report_type {report_type!r}; valid: {REPORT_TYPES}"}
    employees = _load("employees.json")
    if report_type == "workforce_summary":
        by_dept, by_level = {}, {}
        for e in employees:
            by_dept[e["department"]] = by_dept.get(e["department"], 0) + 1
            by_level[e["level"]] = by_level.get(e["level"], 0) + 1
        return {
            "report_type": report_type,
            "total_headcount": len(employees),
            "headcount_by_department": dict(sorted(by_dept.items())),
            "headcount_by_level": dict(sorted(by_level.items())),
            "avg_tenure_months": round(sum(e["tenure_months"] for e in employees) / len(employees), 1),
            "avg_performance_rating": round(sum(e["performance_rating"] for e in employees) / len(employees), 2),
            "status_counts": {s: sum(1 for e in employees if e["status"] == s)
                              for s in sorted({e["status"] for e in employees})},
        }
    if report_type == "attrition_summary":
        return {"report_type": report_type, "last_12_months": attrition_analysis(months=12),
                "last_18_months": attrition_analysis(months=18)}
    if report_type == "comp_summary":
        bands = _load("comp_bands.json")
        out_of_band = 0
        total_comp = 0
        for e in employees:
            band = bands[e["role_family"]][e["level"]]
            total_comp += e["comp"]
            if e["comp"] < band["min"] or e["comp"] > band["max"]:
                out_of_band += 1
        return {
            "report_type": report_type,
            "total_annual_comp_cost": total_comp,
            "avg_comp": round(total_comp / len(employees), 2),
            "employees_out_of_band": out_of_band,
            "note": "Comp adjustments are recommend-only; escalate for approval.",
        }
    # hiring_pipeline
    roles = _load("roles.json")
    candidates = _load("candidates.json")
    pipeline = []
    for r in roles:
        pool = [c for c in candidates if c["role_id"] == r["role_id"]]
        pipeline.append({"role_id": r["role_id"], "title": r["title"],
                         "status": r["status"], "candidates_in_pipeline": len(pool)})
    return {"report_type": report_type, "open_roles": len(roles), "pipeline": pipeline,
            "total_candidates": len(candidates),
            "note": "All hiring decisions require human approval via approve_hire (escalates)."}


# --------------------------------------------------------------- escalation

def approve_hire(candidate_id=None, **kwargs):
    cand = None
    if candidate_id:
        cand = next((c for c in _load("candidates.json")
                     if c["candidate_id"] == candidate_id), None)
    return {
        "escalated": True,
        "action": "approve_hire",
        "candidate_id": candidate_id,
        "candidate_found": cand is not None,
        "status": "PENDING_HUMAN_APPROVAL",
        "message": ("Hiring decisions are recommend-only for this agent. The offer request for "
                    f"{candidate_id or 'unspecified candidate'} has been routed to the hiring "
                    "manager and HR business partner for human review and sign-off."),
    }


def escalate(reason=None, context=None, **kwargs):
    return {
        "escalated": True,
        "action": "escalate",
        "reason": reason or "unspecified",
        "context": context or "",
        "status": "ROUTED_TO_HUMAN",
        "message": "Escalated to a human reviewer. No autonomous action was taken.",
    }


# ------------------------------------------------------------------- export

TOOLS = [
    Tool(
        name="screen_candidates",
        description=("Rank candidates for an open role using ONLY structured qualifications: "
                     "required-skills match, years of experience, and assessment score. Returns a "
                     "scored shortlist with per-candidate breakdown and reasoning. Never uses names "
                     "or demographic attributes."),
        parameters={"type": "object",
                    "properties": {
                        "role_id": {"type": "string",
                                    "description": "Open role id: ROLE-ENG-01, ROLE-DATA-02, or ROLE-PM-03"},
                        "top_n": {"type": "integer", "description": "Shortlist size (default 5)", "default": 5}},
                    "required": ["role_id"]},
        fn=screen_candidates,
        human_equivalent_minutes=90,
    ),
    Tool(
        name="attrition_analysis",
        description=("Compute turnover from exit records: annualized rate, trend (first vs second "
                     "half of window), top exit drivers, exits by department, average tenure at exit."),
        parameters={"type": "object",
                    "properties": {
                        "department": {"type": "string",
                                       "description": "Optional department filter (Technology, Product & Design, Commercial, Corporate)"},
                        "months": {"type": "integer", "description": "Lookback window in months, 1-18 (default 12)",
                                   "default": 12}},
                    "required": []},
        fn=attrition_analysis,
        human_equivalent_minutes=60,
    ),
    Tool(
        name="comp_benchmark",
        description=("Compare current employee compensation in a role family + level against the "
                     "compensation band (min/mid/max). Flags out-of-band employees and computes "
                     "average compa-ratio."),
        parameters={"type": "object",
                    "properties": {
                        "role_family": {"type": "string", "description": "One of the 12 role families, e.g. Engineering"},
                        "level": {"type": "string", "description": "Level L1-L6"}},
                    "required": ["role_family", "level"]},
        fn=comp_benchmark,
        human_equivalent_minutes=45,
    ),
    Tool(
        name="headcount_model",
        description=("Model an org scenario per department: grow_10pct, freeze, or reduce_5pct. "
                     "Returns headcount and annual comp-cost deltas costed at departmental average comp."),
        parameters={"type": "object",
                    "properties": {"scenario": {"type": "string",
                                                "enum": ["grow_10pct", "freeze", "reduce_5pct"]}},
                    "required": ["scenario"]},
        fn=headcount_model,
        human_equivalent_minutes=75,
    ),
    Tool(
        name="lifecycle_status",
        description=("Look up an employee's lifecycle state: onboarding progress, review cycle "
                     "timing, leave, or offboarding status."),
        parameters={"type": "object",
                    "properties": {"employee_id": {"type": "string", "description": "Employee id, e.g. E-042"}},
                    "required": ["employee_id"]},
        fn=lifecycle_status,
        human_equivalent_minutes=10,
    ),
    Tool(
        name="generate_report",
        description=("Assemble a structured summary report: workforce_summary, attrition_summary, "
                     "comp_summary, or hiring_pipeline."),
        parameters={"type": "object",
                    "properties": {"report_type": {"type": "string", "enum": REPORT_TYPES}},
                    "required": ["report_type"]},
        fn=generate_report,
        human_equivalent_minutes=50,
    ),
    Tool(
        name="approve_hire",
        description=("Route a hiring decision to human approval. This agent NEVER approves hires "
                     "autonomously; every offer requires hiring manager + HR sign-off."),
        parameters={"type": "object",
                    "properties": {"candidate_id": {"type": "string", "description": "Candidate id, e.g. C-017"}},
                    "required": ["candidate_id"]},
        fn=approve_hire,
        human_equivalent_minutes=15,
        escalates=True,
    ),
    Tool(
        name="escalate",
        description=("Generic human gate. Use for any decision outside agent authority, ambiguous "
                     "policy situations, or any request that violates fairness policy (e.g. filtering "
                     "candidates by age, gender, nationality, or name origin)."),
        parameters={"type": "object",
                    "properties": {
                        "reason": {"type": "string", "description": "Why this needs a human"},
                        "context": {"type": "string", "description": "Relevant context for the reviewer"}},
                    "required": ["reason"]},
        fn=escalate,
        human_equivalent_minutes=10,
        escalates=True,
    ),
]

TASK_TYPES = {
    "candidate_screening": 90,
    "attrition_analysis": 60,
    "comp_review": 45,
    "org_modeling": 75,
    "lifecycle_check": 10,
    "reporting": 50,
    "general": 20,
}
