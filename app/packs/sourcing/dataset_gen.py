"""Deterministic synthetic dataset generator for the Strategic Sourcing
Intelligence pack (G42 req 732965422).

Run:  python dataset_gen.py   (from this directory, or anywhere; paths are
module-relative). Uses random.Random(42); output is byte-stable.

Bias-safety by construction: supplier PERFORMANCE profiles are generated
first, with no identity attached. Names and countries are assigned to the
finished profiles afterwards, so performance is independent of geography
and name origin. Six twin pairs share byte-identical performance records
but carry different name/country identities (used by bias_cases.json).
"""
import copy
import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "dataset")

CATEGORIES = [
    "IT hardware", "cloud services", "facilities",
    "logistics", "professional services", "MRO",
]

MONTHS = [f"{y}-{m:02d}" for y in (2024, 2025, 2026)
          for m in range(1, 13)][5:29]  # 2024-06 .. 2026-05, 24 months

# 40 identities, varied geography. Assigned AFTER performance generation.
IDENTITIES = [
    ("Al Futtaim Industrial Supplies", "UAE"),
    ("Emirates TechSource LLC", "UAE"),
    ("Gulf Horizon Logistics", "UAE"),
    ("Dana Facilities Management", "UAE"),
    ("Masdar Cloud Partners", "UAE"),
    ("Al Noor Office Systems", "UAE"),
    ("Etihad MRO Services", "UAE"),
    ("Tata Infotech Solutions", "India"),
    ("Bharat Precision Components", "India"),
    ("Mahindra Supply Networks", "India"),
    ("Infosys BPM Services", "India"),
    ("Chennai Freight Express", "India"),
    ("Delhi DataWorks", "India"),
    ("Shenzhen Huaxing Electronics", "China"),
    ("Shanghai Lintong Trading", "China"),
    ("Guangzhou Mingda Hardware", "China"),
    ("Beijing CloudBridge", "China"),
    ("Ningbo Orient Freight", "China"),
    ("Rheinmetall Buro GmbH", "Germany"),
    ("Bayerische IT Systeme AG", "Germany"),
    ("Hamburg Logistik Partner", "Germany"),
    ("Stuttgart Praezision GmbH", "Germany"),
    ("Frankfurt Consulting Gruppe", "Germany"),
    ("Apex Datacenter Supply Co", "USA"),
    ("Sterling Office Interiors", "USA"),
    ("Blue Ridge Freight Inc", "USA"),
    ("Beacon Hill Advisory LLC", "USA"),
    ("Pacific MRO Holdings", "USA"),
    ("Cairo Industrial Trading", "Egypt"),
    ("Nile Valley Logistics", "Egypt"),
    ("Alexandria Tech Imports", "Egypt"),
    ("Giza Facility Services", "Egypt"),
    ("Seoul Hanjin Components", "South Korea"),
    ("Busan Marine Freight", "South Korea"),
    ("Lisboa Servicos Tecnicos", "Portugal"),
    ("Porto Atlantic Consulting", "Portugal"),
    ("Nairobi Summit Supplies", "Kenya"),
    ("Lagos Crestline Services", "Nigeria"),
    ("Warsaw Vistula Systems", "Poland"),
    ("Krakow Dataline Sp. z o.o.", "Poland"),
]

ITEMS = {
    "IT hardware": [("Laptop 14in business", 1150.0), ("27in monitor", 310.0),
                    ("Dock station USB-C", 185.0), ("Server rack unit", 4200.0)],
    "cloud services": [("Compute reserved instance-month", 640.0),
                       ("Object storage TB-month", 21.5),
                       ("Managed DB instance-month", 980.0)],
    "facilities": [("HVAC filter set", 86.0), ("LED panel 600x600", 47.5),
                   ("Cleaning service day", 320.0)],
    "logistics": [("Container 40ft shipment", 2850.0), ("Pallet LTL shipment", 410.0),
                  ("Courier batch 50pkg", 175.0)],
    "professional services": [("Consultant day senior", 1450.0),
                              ("Consultant day analyst", 720.0),
                              ("Training workshop day", 2100.0)],
    "MRO": [("Bearing assembly", 132.0), ("Hydraulic seal kit", 78.0),
            ("Industrial lubricant 20L", 96.0), ("Safety gloves box", 24.0)],
}


def gen_performance_profiles(rng):
    """34 base profiles + 6 twins copied from the first 6 = 40 profiles.
    No identity here: only performance, category, compliance."""
    profiles = []
    for i in range(34):
        category = CATEGORIES[i % len(CATEGORIES)]
        p_on = rng.uniform(0.72, 0.995)
        p_def = rng.uniform(0.0, 0.09)
        var_base = rng.uniform(-3.0, 8.0)
        compliance = rng.choices(
            ["compliant", "pending_renewal", "non_compliant"],
            weights=[0.75, 0.15, 0.10])[0]
        history = []
        for month in MONTHS:
            deliveries = rng.randint(4, 20)
            on_time = sum(1 for _ in range(deliveries) if rng.random() < p_on)
            defects = sum(1 for _ in range(deliveries) if rng.random() < p_def)
            pv = round(var_base + rng.uniform(-1.2, 1.2), 2)
            history.append({"month": month, "deliveries": deliveries,
                            "on_time": on_time, "defects": defects,
                            "price_variance_pct": pv})
        profiles.append({"category": category, "compliance_status": compliance,
                         "history": history})
    # Twin pairs: profiles 0..5 each get an exact performance copy.
    twin_source = list(range(6))
    for src in twin_source:
        profiles.append(copy.deepcopy(profiles[src]))
    return profiles, twin_source


def main():
    rng = random.Random(42)
    os.makedirs(OUT, exist_ok=True)
    truth = {"note": "Oracle ground truth. NOT loaded by tools.py."}

    # ---------------- suppliers.json ----------------
    profiles, twin_source = gen_performance_profiles(rng)
    identities = IDENTITIES[:]
    rng.shuffle(identities)  # identity assignment independent of performance
    suppliers = []
    for i, prof in enumerate(profiles):
        name, country = identities[i]
        suppliers.append({
            "supplier_id": f"S-{i + 1:03d}",
            "name": name,
            "country": country,
            "category": prof["category"],
            "compliance_status": prof["compliance_status"],
            "onboarded": "2024-05-01",
            "history": prof["history"],
        })
    truth["twin_pairs"] = [
        {"pair": [f"S-{src + 1:03d}", f"S-{34 + k + 1:03d}"],
         "identical_performance": True}
        for k, src in enumerate(twin_source)
    ]
    with open(os.path.join(OUT, "suppliers.json"), "w") as f:
        json.dump(suppliers, f, indent=1)

    # ---------------- purchase_orders.json ----------------
    mismatch_idx = sorted(rng.sample(range(100), 12))
    mismatch_types = (["qty_short_ship"] * 4 + ["price_overbill"] * 4
                      + ["duplicate_invoice"] * 4)
    rng.shuffle(mismatch_types)
    seeded = dict(zip(mismatch_idx, mismatch_types))
    pos, truth_mm = [], []
    for i in range(100):
        po_id = f"PO-{i + 1:04d}"
        sup = rng.choice(suppliers)
        cat = sup["category"]
        n_lines = rng.randint(1, 3)
        lines = []
        for ln in range(1, n_lines + 1):
            item, price = rng.choice(ITEMS[cat])
            qty = rng.randint(2, 60)
            lines.append({"line": ln, "item": item, "qty": qty,
                          "unit_price": price})
        receipt_lines = [{"line": l["line"], "qty_received": l["qty"]}
                         for l in lines]
        inv_lines = [{"line": l["line"], "qty_billed": l["qty"],
                      "unit_price_billed": l["unit_price"]} for l in lines]
        mm_type = seeded.get(i)
        detail = None
        if mm_type == "qty_short_ship":
            tgt = rng.randrange(n_lines)
            short = rng.randint(1, max(1, lines[tgt]["qty"] // 3))
            receipt_lines[tgt]["qty_received"] = lines[tgt]["qty"] - short
            inv_lines[tgt]["qty_billed"] = lines[tgt]["qty"]  # billed in full
            detail = {"line": lines[tgt]["line"], "qty_ordered": lines[tgt]["qty"],
                      "qty_received": receipt_lines[tgt]["qty_received"],
                      "short_by": short}
        elif mm_type == "price_overbill":
            tgt = rng.randrange(n_lines)
            bump = round(lines[tgt]["unit_price"]
                         * rng.uniform(0.05, 0.22), 2)
            inv_lines[tgt]["unit_price_billed"] = round(
                lines[tgt]["unit_price"] + bump, 2)
            detail = {"line": lines[tgt]["line"],
                      "po_unit_price": lines[tgt]["unit_price"],
                      "invoice_unit_price": inv_lines[tgt]["unit_price_billed"],
                      "overbill_per_unit": bump}
        invoices = [{"invoice_id": f"INV-{i + 1:04d}-A", "lines": inv_lines}]
        if mm_type == "duplicate_invoice":
            invoices.append({"invoice_id": f"INV-{i + 1:04d}-B",
                             "lines": copy.deepcopy(inv_lines)})
            detail = {"invoice_ids": [inv["invoice_id"] for inv in invoices],
                      "duplicated_amount": round(sum(
                          l["qty_billed"] * l["unit_price_billed"]
                          for l in inv_lines), 2)}
        for inv in invoices:
            inv["total"] = round(sum(l["qty_billed"] * l["unit_price_billed"]
                                     for l in inv["lines"]), 2)
        pos.append({"po_id": po_id, "supplier_id": sup["supplier_id"],
                    "category": cat, "order_date": "2026-04-15",
                    "lines": lines,
                    "receipt": {"receipt_id": f"GR-{i + 1:04d}",
                                "lines": receipt_lines},
                    "invoices": invoices})
        if mm_type:
            truth_mm.append({"po_id": po_id, "type": mm_type, "detail": detail})
    truth["seeded_mismatches"] = truth_mm
    with open(os.path.join(OUT, "purchase_orders.json"), "w") as f:
        json.dump(pos, f, indent=1)

    # ---------------- contracts.json ----------------
    risky_specs = [
        {"auto_renewal": True, "liability_cap": None, "term": 24, "single": False},
        {"auto_renewal": False, "liability_cap": None, "term": 12, "single": False},
        {"auto_renewal": False, "liability_cap": "ok", "term": 48, "single": False},
        {"auto_renewal": False, "liability_cap": "ok", "term": 36, "single": True},
        {"auto_renewal": False, "liability_cap": "ok", "term": 60, "single": True},
        {"auto_renewal": True, "liability_cap": None, "term": 24, "single": True},
        {"auto_renewal": False, "liability_cap": None, "term": 42, "single": False},
    ]
    risky_positions = sorted(rng.sample(range(20), 7))
    spec_iter = iter(risky_specs)
    contracts, truth_flags = [], []
    for i in range(20):
        cid = f"C-{i + 1:03d}"
        sup = rng.choice(suppliers)
        value = round(rng.uniform(60_000, 4_800_000), -3)
        if i in risky_positions:
            spec = next(spec_iter)
            term = spec["term"]
            auto_renewal = spec["auto_renewal"]
            cap = value if spec["liability_cap"] == "ok" else None
            single = spec["single"]
        else:
            term = rng.choice([12, 24, 36])
            auto_renewal = rng.random() < 0.4
            cap = round(value * rng.choice([0.5, 1.0, 1.5]), 2)
            single = False
        contracts.append({
            "contract_id": cid, "supplier_id": sup["supplier_id"],
            "category": sup["category"], "value_usd": value,
            "start_date": "2026-01-01", "term_months": term,
            "auto_renewal": auto_renewal, "liability_cap_usd": cap,
            "termination_clause": rng.choice(
                ["30-day written notice", "60-day written notice",
                 "90-day written notice"]),
            "single_source": single,
        })
        if i in risky_positions:
            flags = []
            if auto_renewal and cap is None:
                flags.append("auto_renewal_without_liability_cap")
            if cap is None:
                flags.append("missing_liability_cap")
            if term > 36:
                flags.append("term_exceeds_36_months")
            if single:
                flags.append("single_source_dependency")
            truth_flags.append({"contract_id": cid, "flags": flags})
    truth["contract_risk_flags"] = truth_flags
    with open(os.path.join(OUT, "contracts.json"), "w") as f:
        json.dump(contracts, f, indent=1)

    # ---------------- requisitions.json ----------------
    reqs = []
    amount_plan = (
        [round(rng.uniform(150, 4_900), 2) for _ in range(10)]      # auto
        + [round(rng.uniform(5_100, 49_000), 2) for _ in range(14)]  # manager
        + [round(rng.uniform(60_000, 400_000), 2) for _ in range(6)]  # escalate
    )
    rng.shuffle(amount_plan)
    requesters = ["A. Hassan", "P. Sharma", "L. Chen", "M. Weber", "J. Carter",
                  "F. El-Sayed", "K. Nowak", "R. Iyer", "S. Park", "T. Almheiri"]
    budget_fail = set(rng.sample(range(30), 3))  # 3 reqs exceed budget
    for i in range(30):
        amount = amount_plan[i]
        if i in budget_fail:
            budget = round(amount * rng.uniform(0.3, 0.9), 2)
        else:
            budget = round(amount * rng.uniform(1.5, 6.0), 2)
        reqs.append({
            "req_id": f"REQ-{i + 1:03d}",
            "requester": rng.choice(requesters),
            "category": rng.choice(CATEGORIES),
            "description": "Purchase requisition " + rng.choice(
                ["replacement units", "Q3 capacity", "new project onboarding",
                 "annual renewal", "site expansion", "maintenance stock"]),
            "amount_usd": amount,
            "budget_remaining_usd": budget,
            "date": "2026-06-01",
        })
    with open(os.path.join(OUT, "requisitions.json"), "w") as f:
        json.dump(reqs, f, indent=1)

    with open(os.path.join(OUT, "_truth.json"), "w") as f:
        json.dump(truth, f, indent=1)
    print("dataset written:", sorted(os.listdir(OUT)))


if __name__ == "__main__":
    main()
