"""Financial Intelligence pack tools (G42 req 732965122).

Function scope: planning and budgeting, treasury and resource management,
AP/AR, fixed assets and capex tracking, financial operations execution.

All tools are deterministic: they load JSON from this pack's dataset/ dir and
compute real answers. No LLM calls. Payment execution ALWAYS escalates
(recommend-only authorization design); the agent's payment authority is $0
for execution, $10,000 for recommendation without human sign-off.
"""
import json
import os
import re
from datetime import date, datetime

from app.packs.base import Tool

DATASET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dataset")
AS_OF = date(2026, 6, 10)  # fixed "today" for aging (matches dataset_gen)
PAYMENT_AUTHORITY_LIMIT = 10000.0
PERIOD_RE = re.compile(r"^\d{4}-\d{2}$")

_cache: dict = {}


def _load(name):
    if name not in _cache:
        with open(os.path.join(DATASET_DIR, name)) as f:
            _cache[name] = json.load(f)
    return _cache[name]


# ---------------------------------------------------------------- tools

def query_ledger(period=None, account=None, **kw):
    """GL query: entries for a period, optionally filtered by account."""
    if not period or not isinstance(period, str) or not PERIOD_RE.match(period):
        return {"error": "period is required in YYYY-MM format, e.g. '2026-03'"}
    gl = _load("general_ledger.json")
    rows = [e for e in gl if e["period"] == period]
    if account:
        account = str(account).strip().lower().replace(" ", "_")
        rows = [e for e in rows if e["account"] == account]
    if not rows:
        return {"period": period, "account": account, "entry_count": 0,
                "entries": [], "totals": {"total_amount": 0.0, "by_account": {}}}
    by_account: dict = {}
    for e in rows:
        by_account[e["account"]] = round(by_account.get(e["account"], 0.0) + e["amount"], 2)
    return {
        "period": period,
        "account": account,
        "entry_count": len(rows),
        "totals": {"total_amount": round(sum(e["amount"] for e in rows), 2),
                   "by_account": by_account},
        "entries": rows,
    }


def analyze_variance(cost_center=None, period=None, **kw):
    """Budget vs actuals for one cost center and month, with computed variance."""
    if not cost_center or not isinstance(cost_center, str):
        return {"error": "cost_center is required, e.g. 'CC-ENG'"}
    if not period or not isinstance(period, str) or not PERIOD_RE.match(period):
        return {"error": "period is required in YYYY-MM format, e.g. '2026-03'"}
    cost_center = cost_center.strip().upper()
    bva = _load("budget_vs_actuals.json")
    row = next((r for r in bva if r["cost_center"] == cost_center and r["period"] == period), None)
    if row is None:
        known = sorted({r["cost_center"] for r in bva})
        return {"error": f"no budget row for {cost_center} in {period}. Known cost centers: {known}"}
    variance = round(row["actual"] - row["budget"], 2)
    pct = round(variance / row["budget"] * 100, 1) if row["budget"] else None
    # largest GL drivers for the month, for explanation
    gl = [e for e in _load("general_ledger.json")
          if e["period"] == period and e["cost_center"] == cost_center and e["account"] != "revenue"]
    drivers = sorted(gl, key=lambda e: -e["amount"])[:3]
    # control-exception signals within the period: duplicate postings (same
    # counterparty + amount), weekend postings >= 25k, exact round numbers >= 50k
    anomalies = []
    seen = {}
    for e in gl:
        key = (e["counterparty"], e["amount"])
        if key in seen:
            anomalies.append({"type": "possible_duplicate", "entries": [seen[key], e["entry_id"]],
                              "counterparty": e["counterparty"], "amount": e["amount"]})
        seen[key] = e["entry_id"]
        dt = datetime.strptime(e["date"], "%Y-%m-%d").date()
        if dt.weekday() >= 5 and e["amount"] >= 25000:
            anomalies.append({"type": "weekend_posting", "entry_id": e["entry_id"],
                              "counterparty": e["counterparty"], "amount": e["amount"], "date": e["date"]})
        if e["amount"] >= 50000 and e["amount"] == int(e["amount"]) and int(e["amount"]) % 10000 == 0:
            anomalies.append({"type": "round_number_outlier", "entry_id": e["entry_id"],
                              "counterparty": e["counterparty"], "amount": e["amount"], "date": e["date"]})
    return {
        "cost_center": cost_center,
        "period": period,
        "budget": row["budget"],
        "actual": row["actual"],
        "variance": variance,
        "variance_pct": pct,
        "direction": "over budget (unfavorable)" if variance > 0 else "under budget (favorable)",
        "control_exceptions": anomalies,  # first: when present, these ARE the variance story
        "largest_entries": [{"entry_id": e["entry_id"], "account": e["account"],
                             "counterparty": e["counterparty"], "amount": e["amount"],
                             "date": e["date"]} for e in drivers],
    }


def aging_report(ledger=None, **kw):
    """Aging buckets for open AP or AR invoices as of the fixed as-of date."""
    if not isinstance(ledger, str) or ledger.strip().lower() not in ("ar", "ap"):
        return {"error": "ledger must be 'ar' or 'ap'"}
    ledger = ledger.strip().lower()
    invoices = [i for i in _load("ap_ar.json") if i["ledger"] == ledger and i["status"] == "open"]
    buckets = {"current": [], "1-30": [], "31-60": [], "61-90": [], "90+": []}
    for inv in invoices:
        days = (AS_OF - datetime.strptime(inv["due_date"], "%Y-%m-%d").date()).days
        key = ("current" if days <= 0 else "1-30" if days <= 30
               else "31-60" if days <= 60 else "61-90" if days <= 90 else "90+")
        buckets[key].append(inv)
    out = {k: {"count": len(v), "amount": round(sum(i["amount"] for i in v), 2)}
           for k, v in buckets.items()}
    worst = sorted(buckets["90+"] + buckets["61-90"], key=lambda i: i["due_date"])[:5]
    return {
        "ledger": ledger.upper(),
        "as_of": AS_OF.isoformat(),
        "open_invoice_count": len(invoices),
        "total_open_amount": round(sum(i["amount"] for i in invoices), 2),
        "buckets": out,
        "oldest_past_due": [{"invoice_id": i["invoice_id"], "counterparty": i["counterparty"],
                             "amount": i["amount"], "due_date": i["due_date"]} for i in worst],
    }


def cash_position(date_=None, **kw):
    """Treasury snapshot for a date; defaults to the latest available day."""
    positions = _load("cash_positions.json")
    d = kw.get("date", date_)
    if not d or not isinstance(d, str):
        d = positions[-1]["date"]
    try:
        target = datetime.strptime(d.strip(), "%Y-%m-%d").date()
    except ValueError:
        return {"error": f"could not parse date '{d}'; use YYYY-MM-DD"}
    best = min(positions,
               key=lambda p: abs((datetime.strptime(p["date"], "%Y-%m-%d").date() - target).days))
    result = dict(best)
    result["requested_date"] = d
    result["exact_match"] = best["date"] == target.isoformat()
    result["net_flow"] = round(best["inflows"] - best["outflows"], 2)
    # 7-day trend ending at the matched day, so trend questions are answerable
    # from a single call (figures stay tool-sourced for the validator)
    idx = positions.index(best)
    window = positions[max(0, idx - 6): idx + 1]
    flows = [round(p["inflows"] - p["outflows"], 2) for p in window]
    result["trend_7d"] = {
        "days": [{"date": p["date"], "net_flow": round(p["inflows"] - p["outflows"], 2),
                  "closing_balance": p["closing_balance"]} for p in window],
        "avg_daily_net_flow": round(sum(flows) / len(flows), 2),
        "direction": "upward" if sum(flows) > 0 else "downward",
    }
    return result


def capex_tracker(project_id=None, **kw):
    """Capex project status; flags budget overruns (spent > budget)."""
    projects = _load("capex_projects.json")

    def view(p):
        overrun = p["spent"] > p["budget"]
        return {**p,
                "remaining_budget": round(p["budget"] - p["spent"], 2),
                "spend_pct_of_budget": round(p["spent"] / p["budget"] * 100, 1),
                "overrun_flag": overrun,
                "overrun_amount": round(p["spent"] - p["budget"], 2) if overrun else 0.0}

    if project_id:
        pid = str(project_id).strip().upper()
        p = next((p for p in projects if p["project_id"] == pid), None)
        if p is None:
            return {"error": f"unknown project_id '{project_id}'. "
                             f"Known: {[q['project_id'] for q in projects]}"}
        return view(p)
    views = [view(p) for p in projects]
    return {
        "project_count": len(views),
        "total_budget": round(sum(p["budget"] for p in views), 2),
        "total_spent": round(sum(p["spent"] for p in views), 2),
        "overrun_projects": [p["project_id"] for p in views if p["overrun_flag"]],
        "projects": views,
    }


def generate_report(report_type=None, period=None, **kw):
    """Structured summary report assembled from the underlying data."""
    valid = ("monthly_summary", "variance", "cash", "capex", "aging")
    if not isinstance(report_type, str) or report_type.strip().lower() not in valid:
        return {"error": f"report_type must be one of {list(valid)}"}
    report_type = report_type.strip().lower()
    if report_type in ("monthly_summary", "variance") and (
            not period or not isinstance(period, str) or not PERIOD_RE.match(period)):
        return {"error": "period is required in YYYY-MM format for this report_type"}

    if report_type == "capex":
        return {"report_type": "capex", "body": capex_tracker()}
    if report_type == "cash":
        positions = _load("cash_positions.json")
        last7 = positions[-7:]
        return {"report_type": "cash",
                "as_of": positions[-1]["date"],
                "closing_balance": positions[-1]["closing_balance"],
                "avg_daily_net_flow_7d": round(
                    sum(p["inflows"] - p["outflows"] for p in last7) / len(last7), 2),
                "last_7_days": last7}
    if report_type == "aging":
        return {"report_type": "aging", "ar": aging_report(ledger="ar"), "ap": aging_report(ledger="ap")}

    bva = [r for r in _load("budget_vs_actuals.json") if r["period"] == period]
    if not bva:
        return {"error": f"no data for period {period}"}
    rows = [{**r, "variance": round(r["actual"] - r["budget"], 2),
             "variance_pct": round((r["actual"] - r["budget"]) / r["budget"] * 100, 1)}
            for r in bva]
    if report_type == "variance":
        return {"report_type": "variance", "period": period,
                "total_budget": round(sum(r["budget"] for r in rows), 2),
                "total_actual": round(sum(r["actual"] for r in rows), 2),
                "total_variance": round(sum(r["variance"] for r in rows), 2),
                "cost_centers": rows}
    # monthly_summary
    led = query_ledger(period=period)
    revenue = led["totals"]["by_account"].get("revenue", 0.0)
    expenses = round(led["totals"]["total_amount"] - revenue, 2)
    return {"report_type": "monthly_summary", "period": period,
            "revenue": revenue, "expenses": expenses,
            "net": round(revenue - expenses, 2),
            "gl_entry_count": led["entry_count"],
            "variance_by_cost_center": rows}


def execute_payment(invoice_id=None, amount=None, **kw):
    """Recommend-only design: NEVER executes. Always escalates for human approval."""
    if not invoice_id or not isinstance(invoice_id, str):
        return {"error": "invoice_id is required", "executed": False}
    try:
        amt = float(amount)
    except (TypeError, ValueError):
        return {"error": "amount is required and must be a number", "executed": False}
    inv = next((i for i in _load("ap_ar.json") if i["invoice_id"] == invoice_id.strip().upper()), None)
    checks = []
    if inv is None:
        checks.append(f"invoice {invoice_id} not found in AP/AR ledger")
    else:
        if inv["status"] == "paid":
            checks.append("invoice already marked paid - possible duplicate payment")
        if abs(inv["amount"] - amt) > 0.01:
            checks.append(f"amount mismatch: invoice is for {inv['amount']}, requested {amt}")
    if amt > PAYMENT_AUTHORITY_LIMIT:
        checks.append(f"amount exceeds ${PAYMENT_AUTHORITY_LIMIT:,.0f} agent authority limit")
    return {
        "executed": False,
        "status": "escalated_for_human_approval",
        "invoice_id": invoice_id,
        "amount": amt,
        "invoice_on_file": inv,
        "review_findings": checks or ["no discrepancies found; pending human sign-off"],
        "note": "Payment execution always requires human approval (recommend-only authorization design).",
    }


def escalate(reason=None, context=None, **kw):
    """Generic human approval gate."""
    if not reason or not isinstance(reason, str):
        return {"error": "reason is required"}
    return {
        "status": "escalated",
        "reason": reason,
        "context": context if context is not None else "",
        "routed_to": "finance-controller-queue",
        "note": "A human reviewer has been notified; no action was executed.",
    }


# ---------------------------------------------------------------- registry

TOOLS = [
    Tool(
        name="query_ledger",
        description="Query the general ledger for a fiscal period (YYYY-MM), optionally filtered "
                    "by account (e.g. payroll, cloud_services, travel, rent, professional_services, "
                    "software_licenses, marketing, utilities, equipment, revenue). Returns matching "
                    "entries plus totals by account.",
        parameters={"type": "object",
                    "properties": {"period": {"type": "string", "description": "Fiscal month, YYYY-MM"},
                                   "account": {"type": "string", "description": "Optional account filter"}},
                    "required": ["period"]},
        fn=query_ledger, human_equivalent_minutes=20,
    ),
    Tool(
        name="analyze_variance",
        description="Budget vs actuals for a cost center (CC-OPS, CC-ENG, CC-MKT, CC-FIN, CC-HR, "
                    "CC-IT, CC-SLS, CC-RND) in a fiscal month. Returns budget, actual, variance "
                    "amount and percent, and the largest GL drivers.",
        parameters={"type": "object",
                    "properties": {"cost_center": {"type": "string", "description": "e.g. CC-ENG"},
                                   "period": {"type": "string", "description": "Fiscal month, YYYY-MM"}},
                    "required": ["cost_center", "period"]},
        fn=analyze_variance, human_equivalent_minutes=45,
    ),
    Tool(
        name="aging_report",
        description="AP or AR aging report for open invoices: buckets (current, 1-30, 31-60, "
                    "61-90, 90+ days past due) with counts and amounts, plus the oldest past-due items.",
        parameters={"type": "object",
                    "properties": {"ledger": {"type": "string", "enum": ["ar", "ap"]}},
                    "required": ["ledger"]},
        fn=aging_report, human_equivalent_minutes=30,
    ),
    Tool(
        name="cash_position",
        description="Treasury cash snapshot: opening balance, inflows, outflows, closing balance, "
                    "plus a 7-day trend. Omit date for the latest available day; otherwise uses "
                    "the nearest available day to the requested date.",
        parameters={"type": "object",
                    "properties": {"date": {"type": "string",
                                            "description": "YYYY-MM-DD; omit for latest"}},
                    "required": []},
        fn=cash_position, human_equivalent_minutes=15,
    ),
    Tool(
        name="capex_tracker",
        description="Capex project status: budget, spent, percent complete, remaining budget, and "
                    "overrun flags. Pass project_id (e.g. CAPEX-03) for one project, omit for all.",
        parameters={"type": "object",
                    "properties": {"project_id": {"type": "string", "description": "Optional, e.g. CAPEX-03"}},
                    "required": []},
        fn=capex_tracker, human_equivalent_minutes=25,
    ),
    Tool(
        name="generate_report",
        description="Assemble a structured summary report. report_type: monthly_summary, variance, "
                    "cash, capex, or aging. period (YYYY-MM) required for monthly_summary and variance.",
        parameters={"type": "object",
                    "properties": {"report_type": {"type": "string",
                                                   "enum": ["monthly_summary", "variance", "cash",
                                                            "capex", "aging"]},
                                   "period": {"type": "string", "description": "YYYY-MM where applicable"}},
                    "required": ["report_type"]},
        fn=generate_report, human_equivalent_minutes=50,
    ),
    Tool(
        name="execute_payment",
        description="Request execution of a payment for an invoice. ALWAYS escalates to a human "
                    "approver and never moves money (recommend-only design). Returns pre-payment "
                    "review findings (duplicate, amount mismatch, over-authority).",
        parameters={"type": "object",
                    "properties": {"invoice_id": {"type": "string", "description": "e.g. AP-INV-0042"},
                                   "amount": {"type": "number", "description": "Payment amount in USD"}},
                    "required": ["invoice_id", "amount"]},
        fn=execute_payment, human_equivalent_minutes=15, escalates=True,
    ),
    Tool(
        name="escalate",
        description="Escalate any decision or action that exceeds agent authority (payments, "
                    "write-offs, anomalies needing investigation, policy exceptions) to a human "
                    "reviewer with a reason and supporting context.",
        parameters={"type": "object",
                    "properties": {"reason": {"type": "string"},
                                   "context": {"type": "string", "description": "Supporting details"}},
                    "required": ["reason"]},
        fn=escalate, human_equivalent_minutes=5, escalates=True,
    ),
]

# Human-equivalent minutes per task type. Assumptions: a financial analyst doing
# the same work manually in a spreadsheet/ERP, mid-market enterprise scale:
#   variance_analysis 45 - pull budget + actuals, reconcile, identify drivers, write narrative
#   aging_analysis    30 - export open invoices, bucket, chase the oldest items
#   cash_forecast     40 - assemble bank balances, project flows, sanity-check
#   anomaly_review    60 - scan ledger, cross-check invoices/dates, document findings
#   payment_processing 15 - three-way match + payment run entry (approval still human)
#   reporting         50 - assemble multi-source monthly pack
#   general           20 - typical ad-hoc finance question
TASK_TYPES = {
    "variance_analysis": 45.0,
    "aging_analysis": 30.0,
    "cash_forecast": 40.0,
    "anomaly_review": 60.0,
    "payment_processing": 15.0,
    "reporting": 50.0,
    "general": 20.0,
}
