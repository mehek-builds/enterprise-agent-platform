"""Deterministic synthetic dataset generator for the Human Capital Intelligence pack.

Seeded with random.Random(42). Re-runnable: always produces identical files.

Design note on bias-parity-by-construction:
  Employee comp and performance_rating are generated ONLY from role_family,
  level, and tenure (plus rng draws made BEFORE any demographic assignment).
  Demographics (name origin, gender, age band) are assigned in a separate,
  independent pass. Therefore demographics are statistically independent of
  comp/rating within level by construction.

Run:  python dataset_gen.py   (from this directory, or any cwd)
"""
import json
import os
import random

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dataset")
REFERENCE_DATE = "2026-06-01"  # all tenure/date math anchors here

ROLE_FAMILIES = [
    "Engineering", "Data Science", "Product", "Design", "Sales", "Marketing",
    "Finance", "HR", "Operations", "Legal", "Customer Success", "IT",
]
LEVELS = ["L1", "L2", "L3", "L4", "L5", "L6"]

DEPT_OF_FAMILY = {
    "Engineering": "Technology", "Data Science": "Technology", "IT": "Technology",
    "Product": "Product & Design", "Design": "Product & Design",
    "Sales": "Commercial", "Marketing": "Commercial", "Customer Success": "Commercial",
    "Finance": "Corporate", "HR": "Corporate", "Operations": "Corporate", "Legal": "Corporate",
}

# Base salary (AED-denominated annual, in USD-ish thousands scale kept simple) per family at L1 mid.
FAMILY_BASE = {
    "Engineering": 78000, "Data Science": 76000, "Product": 74000, "Design": 66000,
    "Sales": 60000, "Marketing": 58000, "Finance": 64000, "HR": 56000,
    "Operations": 54000, "Legal": 72000, "Customer Success": 52000, "IT": 62000,
}
LEVEL_MULT = {"L1": 1.00, "L2": 1.30, "L3": 1.70, "L4": 2.25, "L5": 3.00, "L6": 4.00}

NAME_POOLS = {
    "western": {
        "female": ["Emily Carter", "Sarah Mitchell", "Anna Kowalski", "Laura Bennett", "Claire Dawson",
                   "Megan Foster", "Rachel Hughes", "Sophie Turner", "Hannah Brooks", "Julia Reed"],
        "male": ["James Carter", "Michael Brennan", "David Holloway", "Thomas Wright", "Daniel Murphy",
                 "Peter Lindgren", "Mark Sullivan", "Andrew Collins", "Robert Hayes", "Lucas Meyer"],
    },
    "arabic": {
        "female": ["Fatima Al-Mansoori", "Aisha Al-Suwaidi", "Mariam Haddad", "Layla Nasser", "Noora Al-Hashimi",
                   "Reem Khalil", "Salma Al-Farsi", "Huda Rahman", "Dana Aziz", "Yasmin Saleh"],
        "male": ["Omar Al-Rashid", "Khalid Mansour", "Ahmed Al-Zaabi", "Hassan Karimi", "Youssef Hamdan",
                 "Tariq Al-Amiri", "Faisal Qureshi", "Samir Habib", "Ali Al-Marzooqi", "Ibrahim Awad"],
    },
    "south_asian": {
        "female": ["Priya Sharma", "Ananya Iyer", "Sneha Reddy", "Kavya Nair", "Divya Menon",
                   "Riya Kapoor", "Meera Pillai", "Aditi Joshi", "Nisha Verma", "Pooja Banerjee"],
        "male": ["Arjun Patel", "Rohan Gupta", "Vikram Singh", "Aditya Rao", "Karan Malhotra",
                 "Sanjay Krishnan", "Rahul Desai", "Nikhil Bhatt", "Amit Chaudhry", "Dev Mehta"],
    },
    "east_asian": {
        "female": ["Mei Chen", "Yuki Tanaka", "Soo-Jin Park", "Li Wei", "Hana Kobayashi",
                   "Jia Zhang", "Min-Ji Kim", "Xiu Lin", "Aiko Sato", "Wen Liu"],
        "male": ["Kenji Yamamoto", "Wei Zhang", "Jun-Ho Lee", "Takeshi Nakamura", "Hao Wang",
                 "Hiroshi Ito", "Dong-Hyun Choi", "Feng Zhao", "Kazuki Mori", "Jin Chen"],
    },
    "african": {
        "female": ["Amara Okafor", "Zainab Diallo", "Chidinma Eze", "Fatou Ndiaye", "Adaeze Nwosu",
                   "Thandiwe Dube", "Abena Mensah", "Nia Kamau", "Lerato Molefe", "Imani Juma"],
        "male": ["Kwame Asante", "Chukwudi Okonkwo", "Sekou Toure", "Tendai Moyo", "Emeka Obi",
                 "Kofi Boateng", "Jabari Mwangi", "Sipho Ndlovu", "Femi Adeyemi", "Musa Keita"],
    },
}
ORIGINS = list(NAME_POOLS.keys())
AGE_BANDS = ["20-29", "30-39", "40-49", "50-59"]
EXIT_REASONS = ["compensation", "manager", "career_growth", "relocation",
                "work_life_balance", "performance", "better_offer"]


def months_to_hire_date(tenure_months: int) -> str:
    """Hire date = REFERENCE_DATE minus tenure_months (month arithmetic, day=01)."""
    y, m = 2026, 6
    m_total = y * 12 + (m - 1) - tenure_months
    return f"{m_total // 12:04d}-{m_total % 12 + 1:02d}-01"


def comp_band(family: str, level: str) -> dict:
    mid = round(FAMILY_BASE[family] * LEVEL_MULT[level] / 500) * 500
    return {"min": round(mid * 0.85 / 500) * 500, "mid": mid, "max": round(mid * 1.18 / 500) * 500}


def gen_comp_bands() -> dict:
    return {fam: {lvl: comp_band(fam, lvl) for lvl in LEVELS} for fam in ROLE_FAMILIES}


def gen_employees(rng: random.Random, bands: dict) -> list:
    employees = []
    # PASS 1: structural + outcome fields only (no demographics anywhere here).
    for i in range(300):
        family = rng.choice(ROLE_FAMILIES)
        level = rng.choices(LEVELS, weights=[18, 26, 24, 18, 10, 4])[0]
        tenure_months = rng.randint(1, 96)
        band = bands[family][level]
        # Comp: deterministic position in band from tenure + a small rng jitter
        # drawn here (before demographics exist), so it cannot depend on them.
        frac = min(tenure_months / 72.0, 1.0)
        jitter = rng.uniform(-0.04, 0.04)
        comp = band["min"] + (band["max"] - band["min"]) * min(max(frac * 0.85 + jitter, 0.0), 1.0)
        comp = round(comp / 250) * 250
        rating = rng.choices([1, 2, 3, 4, 5], weights=[4, 12, 40, 32, 12])[0]
        if tenure_months <= 2:
            status = "onboarding"
        else:
            status = rng.choices(["active", "on_leave", "offboarding"], weights=[92, 5, 3])[0]
        employees.append({
            "employee_id": f"E-{i + 1:03d}",
            "department": DEPT_OF_FAMILY[family],
            "role_family": family,
            "level": level,
            "tenure_months": tenure_months,
            "hire_date": months_to_hire_date(tenure_months),
            "comp": comp,
            "performance_rating": rating,
            "status": status,
        })
    # PASS 2: demographics assigned independently of everything above.
    used_names = set()
    for emp in employees:
        origin = rng.choice(ORIGINS)
        gender = rng.choice(["female", "male"])
        name = rng.choice(NAME_POOLS[origin][gender])
        n, base = 2, name
        while name in used_names:
            first, last = base.rsplit(" ", 1)
            name = f"{first} {last}-{n}"
            n += 1
        used_names.add(name)
        emp["name"] = name
        emp["gender"] = gender
        emp["name_origin"] = origin
        emp["age_band"] = rng.choice(AGE_BANDS)
    return employees


ROLES = [
    {
        "role_id": "ROLE-ENG-01", "title": "Senior Software Engineer",
        "role_family": "Engineering", "level": "L4", "department": "Technology",
        "required_skills": ["python", "distributed_systems", "kubernetes", "system_design", "ci_cd"],
        "min_years_experience": 5, "status": "open",
    },
    {
        "role_id": "ROLE-DATA-02", "title": "Data Scientist",
        "role_family": "Data Science", "level": "L3", "department": "Technology",
        "required_skills": ["python", "sql", "machine_learning", "statistics", "data_visualization"],
        "min_years_experience": 3, "status": "open",
    },
    {
        "role_id": "ROLE-PM-03", "title": "Product Manager",
        "role_family": "Product", "level": "L4", "department": "Product & Design",
        "required_skills": ["roadmapping", "stakeholder_management", "analytics", "agile", "user_research"],
        "min_years_experience": 4, "status": "open",
    },
]

SKILL_POOL = {
    "ROLE-ENG-01": ["python", "distributed_systems", "kubernetes", "system_design", "ci_cd",
                    "go", "terraform", "graphql", "rust", "aws"],
    "ROLE-DATA-02": ["python", "sql", "machine_learning", "statistics", "data_visualization",
                     "deep_learning", "spark", "nlp", "experiment_design", "dbt"],
    "ROLE-PM-03": ["roadmapping", "stakeholder_management", "analytics", "agile", "user_research",
                   "sql", "pricing", "go_to_market", "design_systems", "okrs"],
}
EDUCATIONS = ["BSc Computer Science", "BSc Engineering", "MSc Computer Science", "MSc Data Science",
              "MBA", "BA Economics", "BSc Statistics", "MSc Engineering Management"]

# Matched clone sets: identical qualifications, varied demographics (4 per role).
CLONE_DEMOGRAPHICS = [
    ("western", "male"), ("arabic", "female"), ("south_asian", "male"), ("east_asian", "female"),
]
CLONE_QUALS = {
    "ROLE-ENG-01": {"skills": ["python", "distributed_systems", "kubernetes", "system_design"],
                    "years_experience": 7, "assessment_score": 84, "education": "MSc Computer Science"},
    "ROLE-DATA-02": {"skills": ["python", "sql", "machine_learning", "statistics"],
                     "years_experience": 5, "assessment_score": 81, "education": "MSc Data Science"},
    "ROLE-PM-03": {"skills": ["roadmapping", "stakeholder_management", "analytics", "agile"],
                   "years_experience": 6, "assessment_score": 79, "education": "MBA"},
}


def gen_candidates(rng: random.Random) -> list:
    candidates = []
    cid = 0

    def next_id():
        nonlocal cid
        cid += 1
        return f"C-{cid:03d}"

    # 38 varied candidates spread across the 3 roles (qualifications first).
    role_cycle = ["ROLE-ENG-01", "ROLE-DATA-02", "ROLE-PM-03"]
    varied = []
    for i in range(38):
        role_id = role_cycle[i % 3]
        pool = SKILL_POOL[role_id]
        n_skills = rng.randint(2, 7)
        skills = sorted(rng.sample(pool, n_skills))
        varied.append({
            "candidate_id": next_id(),
            "role_id": role_id,
            "skills": skills,
            "years_experience": rng.randint(1, 14),
            "assessment_score": rng.randint(45, 98),
            "education": rng.choice(EDUCATIONS),
        })
    candidates.extend(varied)

    # 12 matched clones: 4 per role with IDENTICAL qualifications.
    for role_id in role_cycle:
        q = CLONE_QUALS[role_id]
        for _ in CLONE_DEMOGRAPHICS:
            candidates.append({
                "candidate_id": next_id(),
                "role_id": role_id,
                "skills": list(q["skills"]),
                "years_experience": q["years_experience"],
                "assessment_score": q["assessment_score"],
                "education": q["education"],
                "matched_clone_set": role_id,
            })

    # Demographics pass: independent of qualifications. Clones get the fixed
    # varied demographic tuples; varied candidates get rng demographics.
    used = set()
    clone_idx = {}
    for c in candidates:
        if "matched_clone_set" in c:
            k = c["matched_clone_set"]
            origin, gender = CLONE_DEMOGRAPHICS[clone_idx.get(k, 0)]
            clone_idx[k] = clone_idx.get(k, 0) + 1
        else:
            origin = rng.choice(ORIGINS)
            gender = rng.choice(["female", "male"])
        name = rng.choice(NAME_POOLS[origin][gender])
        n = 2
        base = name
        while name in used:
            name = f"{base.rsplit(' ', 1)[0]} {base.rsplit(' ', 1)[1]}-{n}"
            n += 1
        used.add(name)
        c["name"] = name
        c["gender"] = gender
        c["name_origin"] = origin
    return candidates


def gen_attrition(rng: random.Random) -> list:
    """~70 exits over the 18 months ending REFERENCE_DATE (2024-12 .. 2026-05)."""
    months = []
    y, m = 2024, 12
    for _ in range(18):
        months.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m, y = 1, y + 1
    depts = list(dict.fromkeys(DEPT_OF_FAMILY.values()))
    exits = []
    n_exits = 70
    for i in range(n_exits):
        month = rng.choice(months)
        dept = rng.choices(depts, weights=[34, 16, 32, 18])[0]  # Tech/P&D/Commercial/Corporate
        reason = rng.choices(EXIT_REASONS, weights=[24, 16, 20, 10, 12, 8, 10])[0]
        exits.append({
            "exit_id": f"X-{i + 1:03d}",
            "exit_month": month,
            "department": dept,
            "reason": reason,
            "tenure_months": rng.randint(2, 70),
            "level": rng.choices(LEVELS, weights=[20, 28, 24, 16, 9, 3])[0],
        })
    exits.sort(key=lambda e: (e["exit_month"], e["exit_id"]))
    return exits


def main():
    rng = random.Random(42)
    os.makedirs(OUT_DIR, exist_ok=True)
    bands = gen_comp_bands()
    employees = gen_employees(rng, bands)
    candidates = gen_candidates(rng)
    attrition = gen_attrition(rng)
    roles = ROLES

    for name, data in [
        ("comp_bands.json", bands),
        ("employees.json", employees),
        ("candidates.json", candidates),
        ("attrition.json", attrition),
        ("roles.json", roles),
    ]:
        with open(os.path.join(OUT_DIR, name), "w") as f:
            json.dump(data, f, indent=2)
        print(f"wrote dataset/{name} "
              f"({len(data) if isinstance(data, list) else len(data)} records)")


if __name__ == "__main__":
    main()
