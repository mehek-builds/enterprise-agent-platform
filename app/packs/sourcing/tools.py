"""Strategic Sourcing Intelligence pack tools (G42 req 732965422).

All figures are COMPUTED from dataset/ JSON; nothing is hardcoded.
Currency: USD. Bad arguments return {"error": "..."}.
"""
import json
import os

from app.packs.base import Tool

PACK_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(PACK_DIR, "dataset")

AUTO_APPROVE_LIMIT_USD = 5_000.0
MANAGER_LIMIT_USD = 50_000.0

_cache: dict = {}


def _load(name):
    if name not in _cache:
        with open(os.path.join(DATASET_DIR, name)) as f:
            _cache[name] = json.load(f)
    return _cache[name]


def _supplier(supplier_id):
    return next((s for s in _load("suppliers.json")
                 if s["supplier_id"] == supplier_id), None)


# ---------------------------------------------------------------- scorecard
def _scorecard(s):
    h = s["history"]
    deliveries = sum(m["deliveries"] for m in h)
    on_time = sum(m["on_time"] for m in h)
    defects = sum(m["defects"] for m in h)
    on_time_rate = on_time / deliveries if deliveries else 0.0
    defect_rate = defects / deliveries if deliveries else 0.0
    avg_pv = sum(m["price_variance_pct"] for m in h) / len(h) if h else 0.0
    price_score = max(0.0, 1.0 - max(avg_pv, 0.0) / 10.0)
    compliance_score = {"compliant": 1.0, "pending_renewal": 0.5,
                        "non_compliant": 0.0}[s["compliance_status"]]
    composite = round(100.0 * (0.40 * on_time_rate
                               + 0.30 * (1.0 - defect_rate)
                               + 0.20 * price_score
                               + 0.10 * compliance_score), 1)
    return {
        "supplier_id": s["supplier_id"],
        "name": s["name"],
        "country": s["country"],
        "category": s["category"],
        "months_of_history": len(h),
        "total_deliveries": deliveries,
        "on_time_delivery_rate": round(on_time_rate, 4),
        "defect_rate": round(defect_rate, 4),
        "avg_price_variance_pct": round(avg_pv, 2),
        "compliance_status": s["compliance_status"],
        "composite_score": composite,
        "scoring_formula": ("100 * (0.40*on_time_rate + 0.30*(1-defect_rate) "
                            "+ 0.20*price_score + 0.10*compliance_score); "
                            "price_score = max(0, 1 - max(avg_price_variance_pct,0)/10); "
                            "compliance: compliant=1.0, pending_renewal=0.5, "
                            "non_compliant=0.0"),
    }


def evaluate_supplier(supplier_id=None, **kw):
    if not supplier_id:
        return {"error": "supplier_id is required"}
    s = _supplier(supplier_id)
    if s is None:
        return {"error": f"unknown supplier_id: {supplier_id}"}
    return _scorecard(s)


def intake_requisition(req_id=None, **kw):
    if not req_id:
        return {"error": "req_id is required"}
    r = next((x for x in _load("requisitions.json")
              if x["req_id"] == req_id), None)
    if r is None:
        return {"error": f"unknown req_id: {req_id}"}
    amount = r["amount_usd"]
    budget_ok = amount <= r["budget_remaining_usd"]
    if not budget_ok:
        routing, reason = "escalate", (
            f"amount {amount} USD exceeds remaining budget "
            f"{r['budget_remaining_usd']} USD")
    elif amount < AUTO_APPROVE_LIMIT_USD:
        routing, reason = "auto_approve", (
            f"amount {amount} USD is under the {AUTO_APPROVE_LIMIT_USD:.0f} "
            "USD auto-approve threshold and budget is available")
    elif amount <= MANAGER_LIMIT_USD:
        routing, reason = "category_manager", (
            f"amount {amount} USD is between {AUTO_APPROVE_LIMIT_USD:.0f} and "
            f"{MANAGER_LIMIT_USD:.0f} USD; routed to the "
            f"{r['category']} category manager")
    else:
        routing, reason = "escalate", (
            f"amount {amount} USD exceeds the {MANAGER_LIMIT_USD:.0f} USD "
            "category-manager limit; human approval required")
    return {"req_id": r["req_id"], "requester": r["requester"],
            "category": r["category"], "description": r["description"],
            "amount_usd": amount,
            "budget_remaining_usd": r["budget_remaining_usd"],
            "budget_ok": budget_ok, "routing": routing,
            "routing_reason": reason}


def sourcing_recommendation(category=None, min_score=0, **kw):
    if not category:
        return {"error": "category is required"}
    try:
        min_score = float(min_score)
    except (TypeError, ValueError):
        return {"error": "min_score must be a number"}
    pool = [s for s in _load("suppliers.json") if s["category"] == category]
    if not pool:
        cats = sorted({s["category"] for s in _load("suppliers.json")})
        return {"error": f"unknown category: {category}; valid: {cats}"}
    cards = sorted((_scorecard(s) for s in pool),
                   key=lambda c: (-c["composite_score"], c["supplier_id"]))
    ranked = []
    for rank, c in enumerate(cards, 1):
        if c["composite_score"] < min_score:
            continue
        ranked.append({
            "rank": rank, "supplier_id": c["supplier_id"], "name": c["name"],
            "composite_score": c["composite_score"],
            "on_time_delivery_rate": c["on_time_delivery_rate"],
            "defect_rate": c["defect_rate"],
            "avg_price_variance_pct": c["avg_price_variance_pct"],
            "compliance_status": c["compliance_status"],
            "rationale": (
                f"on-time {c['on_time_delivery_rate']:.1%}, defect rate "
                f"{c['defect_rate']:.1%}, avg price variance "
                f"{c['avg_price_variance_pct']:+.2f}% vs contract, "
                f"compliance {c['compliance_status']}"),
        })
    return {"category": category, "min_score": min_score,
            "suppliers_in_category": len(pool),
            "suppliers_meeting_min_score": len(ranked),
            "ranked_options": ranked,
            "note": ("Ranking is computed strictly from delivery, quality, "
                     "price and compliance data. Awarding any contract "
                     "requires award_contract, which escalates to a human.")}


def contract_review(contract_id=None, **kw):
    if not contract_id:
        return {"error": "contract_id is required"}
    c = next((x for x in _load("contracts.json")
              if x["contract_id"] == contract_id), None)
    if c is None:
        return {"error": f"unknown contract_id: {contract_id}"}
    flags = []
    if c["auto_renewal"] and c["liability_cap_usd"] is None:
        flags.append("auto_renewal_without_liability_cap")
    if c["liability_cap_usd"] is None:
        flags.append("missing_liability_cap")
    if c["term_months"] > 36:
        flags.append("term_exceeds_36_months")
    if c["single_source"]:
        flags.append("single_source_dependency")
    return {
        "contract_id": c["contract_id"], "supplier_id": c["supplier_id"],
        "category": c["category"],
        "key_terms": {
            "value_usd": c["value_usd"],
            "term_months": c["term_months"],
            "start_date": c["start_date"],
            "auto_renewal": c["auto_renewal"],
            "liability_cap_usd": c["liability_cap_usd"],
            "termination_clause": c["termination_clause"],
            "single_source": c["single_source"],
        },
        "risk_flags": flags,
        "risk_level": ("high" if len(flags) >= 2 else
                       "medium" if flags else "low"),
    }


def _match_one(po):
    mismatches = []
    po_lines = {l["line"]: l for l in po["lines"]}
    rec_lines = {l["line"]: l for l in po["receipt"]["lines"]}
    # quantity: ordered vs received
    for ln, l in po_lines.items():
        rec = rec_lines.get(ln, {"qty_received": 0})
        if rec["qty_received"] != l["qty"]:
            mismatches.append({
                "type": "qty_short_ship", "line": ln, "item": l["item"],
                "qty_ordered": l["qty"],
                "qty_received": rec["qty_received"],
                "short_by": l["qty"] - rec["qty_received"]})
    # duplicate invoices
    if len(po["invoices"]) > 1:
        sigs = [json.dumps(inv["lines"], sort_keys=True)
                for inv in po["invoices"]]
        if len(set(sigs)) < len(sigs):
            mismatches.append({
                "type": "duplicate_invoice",
                "invoice_ids": [inv["invoice_id"] for inv in po["invoices"]],
                "duplicated_amount_usd": po["invoices"][1]["total"]})
    # price and billed-qty: invoice vs PO/receipt (first invoice = canonical)
    inv = po["invoices"][0]
    for il in inv["lines"]:
        l = po_lines.get(il["line"])
        if l is None:
            continue
        if abs(il["unit_price_billed"] - l["unit_price"]) > 1e-9:
            mismatches.append({
                "type": "price_overbill", "line": il["line"],
                "item": l["item"], "po_unit_price": l["unit_price"],
                "invoice_unit_price": il["unit_price_billed"],
                "overbill_per_unit": round(
                    il["unit_price_billed"] - l["unit_price"], 2),
                "overbill_total": round(
                    (il["unit_price_billed"] - l["unit_price"])
                    * il["qty_billed"], 2)})
        rec = rec_lines.get(il["line"])
        if rec and il["qty_billed"] > rec["qty_received"]:
            mismatches.append({
                "type": "billed_exceeds_received", "line": il["line"],
                "item": l["item"], "qty_billed": il["qty_billed"],
                "qty_received": rec["qty_received"]})
    return mismatches


def match_goods_receipt(po_id=None, **kw):
    if not po_id:
        return {"error": "po_id is required"}
    po = next((p for p in _load("purchase_orders.json")
               if p["po_id"] == po_id), None)
    if po is None:
        return {"error": f"unknown po_id: {po_id}"}
    mismatches = _match_one(po)
    po_total = round(sum(l["qty"] * l["unit_price"] for l in po["lines"]), 2)
    invoiced_total = round(sum(inv["total"] for inv in po["invoices"]), 2)
    return {"po_id": po["po_id"], "supplier_id": po["supplier_id"],
            "category": po["category"],
            "receipt_id": po["receipt"]["receipt_id"],
            "invoice_ids": [inv["invoice_id"] for inv in po["invoices"]],
            "po_total_usd": po_total, "invoiced_total_usd": invoiced_total,
            "match_status": "matched" if not mismatches else "mismatched",
            "mismatches": mismatches,
            "recommendation": ("clear for payment" if not mismatches else
                               "hold payment; resolve mismatches with supplier")}


def generate_report(report_type=None, **kw):
    if not report_type:
        return {"error": "report_type is required"}
    suppliers = _load("suppliers.json")
    if report_type == "supplier_performance":
        cards = sorted((_scorecard(s) for s in suppliers),
                       key=lambda c: -c["composite_score"])
        by_cat = {}
        for c in cards:
            by_cat.setdefault(c["category"], []).append(
                {"supplier_id": c["supplier_id"],
                 "composite_score": c["composite_score"]})
        return {"report_type": report_type,
                "suppliers_evaluated": len(cards),
                "top_5_overall": [{"supplier_id": c["supplier_id"],
                                   "name": c["name"],
                                   "composite_score": c["composite_score"]}
                                  for c in cards[:5]],
                "bottom_5_overall": [{"supplier_id": c["supplier_id"],
                                      "name": c["name"],
                                      "composite_score": c["composite_score"]}
                                     for c in cards[-5:]],
                "non_compliant_suppliers": [
                    c["supplier_id"] for c in cards
                    if c["compliance_status"] == "non_compliant"],
                "by_category": by_cat}
    if report_type == "three_way_match_exceptions":
        exceptions = []
        for po in _load("purchase_orders.json"):
            mm = _match_one(po)
            if mm:
                exceptions.append({"po_id": po["po_id"],
                                   "supplier_id": po["supplier_id"],
                                   "mismatch_types": sorted(
                                       {m["type"] for m in mm})})
        return {"report_type": report_type,
                "pos_checked": len(_load("purchase_orders.json")),
                "pos_with_exceptions": len(exceptions),
                "exceptions": exceptions}
    if report_type == "contract_risk":
        flagged = []
        for c in _load("contracts.json"):
            r = contract_review(contract_id=c["contract_id"])
            if r["risk_flags"]:
                flagged.append({"contract_id": c["contract_id"],
                                "supplier_id": c["supplier_id"],
                                "value_usd": c["value_usd"],
                                "risk_flags": r["risk_flags"],
                                "risk_level": r["risk_level"]})
        return {"report_type": report_type,
                "contracts_reviewed": len(_load("contracts.json")),
                "contracts_flagged": len(flagged), "flagged": flagged}
    if report_type == "requisition_summary":
        rows = [intake_requisition(req_id=r["req_id"])
                for r in _load("requisitions.json")]
        counts = {}
        for r in rows:
            counts[r["routing"]] = counts.get(r["routing"], 0) + 1
        return {"report_type": report_type, "requisitions": len(rows),
                "routing_counts": counts,
                "total_requested_usd": round(
                    sum(r["amount_usd"] for r in rows), 2),
                "escalations": [r["req_id"] for r in rows
                                if r["routing"] == "escalate"]}
    return {"error": ("unknown report_type; valid: supplier_performance, "
                      "three_way_match_exceptions, contract_risk, "
                      "requisition_summary")}


def award_contract(supplier_id=None, contract_id=None, **kw):
    if not supplier_id or not contract_id:
        return {"error": "supplier_id and contract_id are required"}
    if _supplier(supplier_id) is None:
        return {"error": f"unknown supplier_id: {supplier_id}"}
    if not any(c["contract_id"] == contract_id
               for c in _load("contracts.json")):
        return {"error": f"unknown contract_id: {contract_id}"}
    return {"status": "escalated_to_human",
            "action": "award_contract",
            "supplier_id": supplier_id, "contract_id": contract_id,
            "message": ("Contract awards are never executed autonomously. "
                        "This request has been escalated to the sourcing "
                        "manager for human approval.")}


def escalate(reason=None, context=None, **kw):
    if not reason:
        return {"error": "reason is required"}
    return {"status": "escalated_to_human", "reason": reason,
            "context": context or "",
            "message": "Escalated to a human sourcing manager for review."}


TOOLS = [
    Tool(
        name="evaluate_supplier",
        description=("Compute a supplier performance scorecard from 24 months "
                     "of delivery history: on-time delivery rate, defect "
                     "rate, average price variance vs contract, compliance "
                     "status, and a composite score (0-100)."),
        parameters={"type": "object",
                    "properties": {"supplier_id": {
                        "type": "string",
                        "description": "Supplier ID, e.g. S-001"}},
                    "required": ["supplier_id"]},
        fn=evaluate_supplier, human_equivalent_minutes=60),
    Tool(
        name="intake_requisition",
        description=("Validate, categorize and route a purchase requisition. "
                     "Under 5,000 USD with budget available: auto-approve. "
                     "5,000-50,000 USD with budget: route to category "
                     "manager. Over 50,000 USD or budget exceeded: escalate."),
        parameters={"type": "object",
                    "properties": {"req_id": {
                        "type": "string",
                        "description": "Requisition ID, e.g. REQ-001"}},
                    "required": ["req_id"]},
        fn=intake_requisition, human_equivalent_minutes=20),
    Tool(
        name="sourcing_recommendation",
        description=("Ranked supplier options for a category with rationale "
                     "computed from performance scorecards. Categories: IT "
                     "hardware, cloud services, facilities, logistics, "
                     "professional services, MRO."),
        parameters={"type": "object",
                    "properties": {
                        "category": {"type": "string",
                                     "description": "Sourcing category"},
                        "min_score": {"type": "number", "default": 0,
                                      "description": ("Minimum composite "
                                                      "score filter")}},
                    "required": ["category"]},
        fn=sourcing_recommendation, human_equivalent_minutes=90),
    Tool(
        name="contract_review",
        description=("Extract key contract terms (value, term, renewal, "
                     "liability cap, termination clause) and apply risk "
                     "rules: auto-renewal without liability cap, missing "
                     "liability cap, term over 36 months, single-source "
                     "dependency."),
        parameters={"type": "object",
                    "properties": {"contract_id": {
                        "type": "string",
                        "description": "Contract ID, e.g. C-001"}},
                    "required": ["contract_id"]},
        fn=contract_review, human_equivalent_minutes=120),
    Tool(
        name="match_goods_receipt",
        description=("Run a 3-way match for a purchase order: PO vs goods "
                     "receipt vs invoice(s). Reports exact quantity "
                     "short-ships, price overbills, duplicate invoices and "
                     "billed-exceeds-received exceptions."),
        parameters={"type": "object",
                    "properties": {"po_id": {
                        "type": "string",
                        "description": "Purchase order ID, e.g. PO-0001"}},
                    "required": ["po_id"]},
        fn=match_goods_receipt, human_equivalent_minutes=30),
    Tool(
        name="generate_report",
        description=("Assemble a summary report. report_type one of: "
                     "supplier_performance, three_way_match_exceptions, "
                     "contract_risk, requisition_summary."),
        parameters={"type": "object",
                    "properties": {"report_type": {
                        "type": "string",
                        "enum": ["supplier_performance",
                                 "three_way_match_exceptions",
                                 "contract_risk", "requisition_summary"]}},
                    "required": ["report_type"]},
        fn=generate_report, human_equivalent_minutes=50),
    Tool(
        name="award_contract",
        description=("Request a contract award to a supplier. ALWAYS "
                     "escalates to a human sourcing manager; the agent never "
                     "awards contracts autonomously."),
        parameters={"type": "object",
                    "properties": {
                        "supplier_id": {"type": "string"},
                        "contract_id": {"type": "string"}},
                    "required": ["supplier_id", "contract_id"]},
        fn=award_contract, human_equivalent_minutes=10, escalates=True),
    Tool(
        name="escalate",
        description=("Escalate a decision to a human sourcing manager. Use "
                     "for contract awards, high-value or over-budget "
                     "requisitions, and anything outside policy."),
        parameters={"type": "object",
                    "properties": {
                        "reason": {"type": "string"},
                        "context": {"type": "string"}},
                    "required": ["reason"]},
        fn=escalate, human_equivalent_minutes=5, escalates=True),
]

TASK_TYPES = {
    "supplier_evaluation": 60,
    "requisition_intake": 20,
    "sourcing_decision": 90,
    "contract_review": 120,
    "three_way_match": 30,
    "reporting": 50,
    "general": 20,
}
