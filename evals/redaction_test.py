"""Redaction efficacy: seeded PII tokens vs what the Presidio layer catches.
No LLM calls; measures the redaction layer directly."""
import json
import os

from app.redaction import redact

CASES = [
    ("Please email Fatima Al Mansouri at fatima.almansouri@corp.ae about the Q3 ledger.",
     ["fatima.almansouri@corp.ae", "Fatima Al Mansouri"]),
    ("Candidate phone is +971 50 123 4567 and backup +1 (415) 555-0142.",
     ["+971 50 123 4567", "(415) 555-0142"]),
    ("Wire to IBAN AE070331234567890123456 by Friday.", ["AE070331234567890123456"]),
    ("Card on file 4111 1111 1111 1111 expires next month.", ["4111 1111 1111 1111"]),
    ("SSN on the form reads 856-45-6789.", ["856-45-6789"]),
    ("Server logs show requests from 192.168.4.22 overnight.", ["192.168.4.22"]),
    ("John Smith approved the payment; contact j.smith@vendor.com.",
     ["John Smith", "j.smith@vendor.com"]),
    ("Reach Priya Sharma (priya.s@example.org, +91 98765 43210) for the audit.",
     ["Priya Sharma", "priya.s@example.org", "+91 98765 43210"]),
]


def run() -> dict:
    total = caught = 0
    rows = []
    for text, seeded in CASES:
        red, findings = redact(text)
        for token in seeded:
            total += 1
            hit = token not in red
            caught += hit
            rows.append({"token_type": "seeded", "caught": hit, "text": text[:60]})
    report = {"seeded_pii_tokens": total, "caught": caught,
              "redaction_efficacy": round(caught / total, 3), "rows": rows}
    out = os.path.join(os.path.dirname(__file__), "results", "redaction.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(report, f, indent=2)
    return report


if __name__ == "__main__":
    r = run()
    print(f"redaction efficacy: {r['caught']}/{r['seeded_pii_tokens']} = {r['redaction_efficacy']*100:.0f}%")
