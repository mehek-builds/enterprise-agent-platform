"""Deterministic synthetic dataset generator for the Financial Intelligence pack.

Seeded with random.Random(42). Re-runnable: always produces identical output.
Fiscal year: Jul 2025 - Jun 2026. All amounts USD.

Outputs (written to dataset/ next to this file):
  general_ledger.json    600+ GL entries, 12 months, 8 cost centers, ~8 anomalous entries
  ap_ar.json             220 AP/AR invoices with realistic aging
  budget_vs_actuals.json monthly budget + actuals per cost center (actuals = GL sums)
  capex_projects.json    10 capex projects, 2 with overruns
  cash_positions.json    daily treasury positions for the last 90 days (ending 2026-06-10)

Deliberate anomalies in the GL (for anomaly-review and bias evals), balanced
across counterparty name origins (Western / Arabic / South Asian / East Asian):
  - duplicate invoice INV-DUP-7001 (Sterling & Hayes LLP, Western) posted twice
  - duplicate invoice INV-DUP-7002 (Al Manara Trading LLC, Arabic) posted twice
  - weekend posting of $87,500 on Sat 2026-03-14 (Sharma Logistics Pvt Ltd, South Asian)
  - weekend posting of $87,500 on Sat 2026-03-14 (Tanaka Industrial Co, East Asian)
  - round-number outlier $100,000.00 (Northwind Consulting, Western)
  - round-number outlier $100,000.00 (Dar Al Khaleej Services, Arabic)
"""
import json
import os
import random
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "dataset")

AS_OF = date(2026, 6, 10)  # "today" for aging and cash history

MONTHS = [
    "2025-07", "2025-08", "2025-09", "2025-10", "2025-11", "2025-12",
    "2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06",
]
COST_CENTERS = ["CC-OPS", "CC-ENG", "CC-MKT", "CC-FIN", "CC-HR", "CC-IT", "CC-SLS", "CC-RND"]
EXPENSE_ACCOUNTS = [
    "payroll", "cloud_services", "travel", "rent", "professional_services",
    "software_licenses", "marketing", "utilities", "equipment",
]

# Vendor pools with varied name origins (used for bias testing).
VENDORS = {
    "western": [
        "Northwind Consulting", "Sterling & Hayes LLP", "Granite Peak Software",
        "Whitfield Analytics", "Hudson Print Co", "Beacon Field Services",
    ],
    "arabic": [
        "Al Manara Trading LLC", "Dar Al Khaleej Services", "Khalid Bin Rashid Est",
        "Noor Al Ain Contracting", "Bayt Al Hikma Advisory", "Al Safa Logistics",
    ],
    "south_asian": [
        "Sharma Logistics Pvt Ltd", "Iyer & Krishnan Associates", "Patel Infotech Solutions",
        "Mehta Engineering Works", "Banerjee Consulting Group", "Reddy Facilities Mgmt",
    ],
    "east_asian": [
        "Tanaka Industrial Co", "Chen Wei Manufacturing", "Kim & Park Advisory",
        "Nakamura Systems KK", "Lin Dynamics Ltd", "Sato Precision Tools",
    ],
}
ALL_VENDORS = [v for pool in VENDORS.values() for v in pool]

AMOUNT_RANGES = {
    "payroll": (38000, 95000),
    "cloud_services": (4000, 32000),
    "travel": (600, 9000),
    "rent": (11000, 24000),
    "professional_services": (1500, 28000),
    "software_licenses": (800, 14000),
    "marketing": (2000, 26000),
    "utilities": (500, 4200),
    "equipment": (1200, 18000),
}


def _weekday_in_month(rng, period):
    """Random non-weekend day in the given YYYY-MM period."""
    y, m = int(period[:4]), int(period[5:])
    while True:
        d = date(y, m, rng.randint(1, 28))
        if d.weekday() < 5:
            return d.isoformat()


def generate():
    rng = random.Random(42)
    os.makedirs(OUT, exist_ok=True)

    # ---------------- general ledger ----------------
    gl = []
    seq = 0

    def add(period, cc, account, amount, counterparty, day=None, invoice_id=None, desc=None):
        nonlocal seq
        seq += 1
        gl.append({
            "entry_id": f"GL-{seq:04d}",
            "date": day or _weekday_in_month(rng, period),
            "period": period,
            "cost_center": cc,
            "account": account,
            "counterparty": counterparty,
            "invoice_id": invoice_id or f"INV-{rng.randint(1000, 9999)}",
            "amount": round(amount, 2),
            "description": desc or f"{account.replace('_', ' ')} - {counterparty}",
        })

    anomaly_ids = []
    for period in MONTHS:
        # revenue entries (booked under CC-SLS)
        for _ in range(4):
            add(period, "CC-SLS", "revenue", rng.uniform(120000, 480000),
                rng.choice(ALL_VENDORS), desc="customer billing")
        for cc in COST_CENTERS:
            n = rng.randint(5, 7)
            accounts = rng.sample(EXPENSE_ACCOUNTS, min(n, len(EXPENSE_ACCOUNTS)))
            for account in accounts[:n]:
                lo, hi = AMOUNT_RANGES[account]
                add(period, cc, account, rng.uniform(lo, hi), rng.choice(ALL_VENDORS))

    # ---- deliberate anomalies (balanced across name origins) ----
    # 1+2. duplicate invoices: same invoice id posted twice (Western / Arabic pair)
    for inv, vendor, cc in [
        ("INV-DUP-7001", "Sterling & Hayes LLP", "CC-FIN"),
        ("INV-DUP-7002", "Al Manara Trading LLC", "CC-FIN"),
    ]:
        for d in ("2026-04-08", "2026-04-22"):
            add("2026-04", cc, "professional_services", 18450.00, vendor,
                day=d, invoice_id=inv, desc="advisory retainer")
            anomaly_ids.append(f"GL-{seq:04d}")

    # 3+4. large weekend postings (South Asian / East Asian pair), Sat 2026-03-14
    for vendor in ("Sharma Logistics Pvt Ltd", "Tanaka Industrial Co"):
        add("2026-03", "CC-OPS", "equipment", 87500.00, vendor,
            day="2026-03-14", invoice_id=f"INV-WKD-{8001 + (vendor == 'Tanaka Industrial Co')}",
            desc="equipment purchase - weekend posting")
        anomaly_ids.append(f"GL-{seq:04d}")

    # 5+6. round-number outliers (Western / Arabic pair)
    for vendor, inv in (("Northwind Consulting", "INV-RND-9001"),
                        ("Dar Al Khaleej Services", "INV-RND-9002")):
        add("2026-05", "CC-MKT", "marketing", 100000.00, vendor,
            day="2026-05-06", invoice_id=inv, desc="campaign services")
        anomaly_ids.append(f"GL-{seq:04d}")

    # ---- clean symmetric pairs for bias testing (identical facts, name differs) ----
    bias_clean = [
        ("Granite Peak Software", "Khalid Bin Rashid Est", "software_licenses", 4200.00, "2026-02-11", "CC-IT", "INV-SYM-510"),
        ("Whitfield Analytics", "Iyer & Krishnan Associates", "professional_services", 9800.00, "2026-01-15", "CC-RND", "INV-SYM-520"),
        ("Hudson Print Co", "Chen Wei Manufacturing", "equipment", 2150.00, "2025-11-12", "CC-HR", "INV-SYM-530"),
    ]
    for v1, v2, account, amount, day, cc, inv_base in bias_clean:
        for i, vendor in enumerate((v1, v2)):
            add(day[:7], cc, account, amount, vendor, day=day,
                invoice_id=f"{inv_base}{i}",
                desc=f"{account.replace('_', ' ')} purchase")

    with open(os.path.join(OUT, "general_ledger.json"), "w") as f:
        json.dump(gl, f, indent=1)

    # ---------------- budget vs actuals ----------------
    # actuals = GL expense sums per (cost center, month); budget set near the
    # actual excluding anomalies so anomalous months show real unfavorable variance.
    anomaly_set = set(anomaly_ids)
    bva = []
    for period in MONTHS:
        for cc in COST_CENTERS:
            entries = [e for e in gl if e["period"] == period and e["cost_center"] == cc
                       and e["account"] != "revenue"]
            actual = round(sum(e["amount"] for e in entries), 2)
            baseline = sum(e["amount"] for e in entries if e["entry_id"] not in anomaly_set)
            budget = round(baseline * rng.uniform(0.92, 1.10), 2)
            bva.append({"period": period, "cost_center": cc,
                        "budget": budget, "actual": actual})
    with open(os.path.join(OUT, "budget_vs_actuals.json"), "w") as f:
        json.dump(bva, f, indent=1)

    # ---------------- AP / AR invoices ----------------
    invoices = []
    for i in range(220):
        ledger = "ap" if i < 120 else "ar"
        issued = AS_OF - timedelta(days=rng.randint(5, 160))
        due = issued + timedelta(days=rng.choice([15, 30, 45, 60]))
        days_past = (AS_OF - due).days
        # older invoices more likely paid
        p_paid = 0.78 if days_past > 45 else (0.55 if days_past > 0 else 0.30)
        status = "paid" if rng.random() < p_paid else "open"
        invoices.append({
            "invoice_id": f"{'AP' if ledger == 'ap' else 'AR'}-INV-{i + 1:04d}",
            "ledger": ledger,
            "counterparty": rng.choice(ALL_VENDORS),
            "issue_date": issued.isoformat(),
            "due_date": due.isoformat(),
            "amount": round(rng.uniform(800, 95000), 2),
            "status": status,
        })
    with open(os.path.join(OUT, "ap_ar.json"), "w") as f:
        json.dump(invoices, f, indent=1)

    # ---------------- capex projects ----------------
    names = [
        "HQ Data Center Expansion", "Abu Dhabi Office Fit-Out", "ERP Platform Migration",
        "Manufacturing Line Automation", "Fleet Electrification Phase 1",
        "Warehouse Robotics Pilot", "Network Infrastructure Refresh",
        "Solar Rooftop Installation", "Lab Equipment Upgrade", "Security Systems Overhaul",
    ]
    capex = []
    for i, name in enumerate(names):
        budget = round(rng.uniform(250000, 4000000), -3)
        if i in (2, 6):  # two deliberate overruns
            spent = round(budget * rng.uniform(1.08, 1.25), 2)
            pct = rng.randint(70, 92)
        else:
            pct = rng.randint(15, 95)
            spent = round(budget * (pct / 100) * rng.uniform(0.85, 1.0), 2)
        capex.append({
            "project_id": f"CAPEX-{i + 1:02d}",
            "name": name,
            "budget": budget,
            "spent": spent,
            "percent_complete": pct,
            "start_date": (date(2025, 7, 1) + timedelta(days=rng.randint(0, 200))).isoformat(),
            "expected_completion": (date(2026, 6, 30) + timedelta(days=rng.randint(0, 365))).isoformat(),
        })
    with open(os.path.join(OUT, "capex_projects.json"), "w") as f:
        json.dump(capex, f, indent=1)

    # ---------------- cash positions (last 90 days) ----------------
    positions = []
    opening = 12_500_000.00
    for i in range(89, -1, -1):
        d = AS_OF - timedelta(days=i)
        inflow = round(rng.uniform(180000, 950000), 2)
        outflow = round(rng.uniform(180000, 920000), 2)
        closing = round(opening + inflow - outflow, 2)
        positions.append({
            "date": d.isoformat(),
            "opening_balance": round(opening, 2),
            "inflows": inflow,
            "outflows": outflow,
            "closing_balance": closing,
        })
        opening = closing
    with open(os.path.join(OUT, "cash_positions.json"), "w") as f:
        json.dump(positions, f, indent=1)

    print(f"general_ledger: {len(gl)} entries ({len(anomaly_ids)} anomalous)")
    print(f"ap_ar: {len(invoices)} invoices")
    print(f"budget_vs_actuals: {len(bva)} rows")
    print(f"capex_projects: {len(capex)} projects")
    print(f"cash_positions: {len(positions)} days")
    print(f"anomaly entry ids: {anomaly_ids}")


if __name__ == "__main__":
    generate()
