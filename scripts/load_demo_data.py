#!/usr/bin/env python3
"""Load synthetic demo data into LanceDB for semantic search demonstrations.

Steps:
  1. Generate synthetic resumes and job descriptions into data/synthetic/
  2. Copy demo resume files (.docx/.txt/.pdf) to data/raw_resumes/
  3. Index all copied resumes into the LanceDB vector store (as manager user)
  4. Insert all job descriptions into the jobs table (as manager user)

Usage:
    python scripts/load_demo_data.py
    python scripts/load_demo_data.py --resumes 50 --jds 20
    python scripts/load_demo_data.py --skip-generate   # skip data generation step
    python scripts/load_demo_data.py --wipe            # wipe existing data first
"""

import argparse
import json
import os
import re
import shutil
import sys
import uuid
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / "backend" / ".env")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEMO_USER_ID = "user_manager_789"   # Manager owns all demo data
SYNTHETIC_DIR = PROJECT_ROOT / "data" / "synthetic"
RAW_RESUMES_DIR = PROJECT_ROOT / "data" / "raw_resumes"
N_RESUMES = 300
N_JDS = 100
N_LOCALES: dict = {"india": 100}  # default locale breakdown

# Index all tiered + quality resumes for demo (skip weak/invalid/not_resume)
DEMO_RESUME_CATEGORIES = ["junior", "mid", "senior", "architect", "strong", "good"]

# Location lat/lng lookup for common geo values in JDs
GEO_LOOKUP = {
    "San Francisco": (37.7749, -122.4194),
    "New York":      (40.7128, -74.0060),
    "Seattle":       (47.6062, -122.3321),
    "Austin":        (30.2672, -97.7431),
    "London":        (51.5074, -0.1278),
    "Berlin":        (52.5200, 13.4050),
    "Toronto":       (43.6532, -79.3832),
    "Sydney":        (-33.8688, 151.2093),
    "Singapore":     (1.3521, 103.8198),
    "Amsterdam":     (52.3676, 4.9041),
    "Paris":         (48.8566, 2.3522),
    # India
    "Bangalore":     (12.9716, 77.5946),
    "Bengaluru":     (12.9716, 77.5946),
    "Hyderabad":     (17.3850, 78.4867),
    "Mumbai":        (19.0760, 72.8777),
    "Chennai":       (13.0827, 80.2707),
    "Delhi":         (28.6139, 77.2090),
    "Gurugram":      (28.4595, 77.0266),
    "Noida":         (28.5355, 77.3910),
    "Pune":          (18.5204, 73.8567),
    "Kolkata":       (22.5726, 88.3639),
    "Kochi":         (9.9312, 76.2673),
    "Remote":        (0.0, 0.0),
}

BENEFITS = ["Health insurance", "Dental & vision", "401(k) matching", "Unlimited PTO", "Remote-friendly", "Equity/RSUs"]

INDUSTRY_CATEGORY = {
    "software_engineering": "IT",
    "data_science": "IT",
    "devops_cloud": "IT",
    "healthcare_tech": "Healthcare",
    "fintech": "Finance",
    "climate_tech": "Engineering",
    "media_advertising": "Marketing",
    "cybersecurity": "IT",
    "machine_learning": "IT",
    "product_management": "IT",
    "startup_engineering": "IT",
    "startup_generalist": "IT",
    "remote_first": "IT",
    "enterprise_consulting": "Consulting",
}

# Maps synthetic industry keys → _VALID_INDUSTRIES display labels used in resume_meta
INDUSTRY_DISPLAY = {
    "software_engineering": "Technology",
    "data_science":         "Technology",
    "devops_cloud":         "Technology",
    "cybersecurity":        "Technology",
    "machine_learning":     "Technology",
    "product_management":   "Technology",
    "startup_engineering":  "Technology",
    "startup_generalist":   "Technology",
    "remote_first":         "Technology",
    "healthcare_tech":      "Healthcare",
    "fintech":              "Finance",
    "climate_tech":         "Engineering",
    "media_advertising":    "Marketing",
    "enterprise_consulting":"Other",
}

LEVEL_MAP = {
    "Senior": "SENIOR", "Staff": "SENIOR", "Principal": "SENIOR",
    "Junior": "JUNIOR", "Entry": "JUNIOR",
    "Manager": "MANAGER", "Lead": "SENIOR",
}

_SALARY_CURRENCY_MAP = [
    ("£",    "GBP"), ("€",    "EUR"),
    ("CAD$", "CAD"), ("AUD$", "AUD"), ("SGD$", "SGD"),
]


def _infer_level(title: str) -> str:
    for keyword, level in LEVEL_MAP.items():
        if keyword.lower() in title.lower():
            return level
    return "MID"


def _infer_geo(location_str: str):
    for city, coords in GEO_LOOKUP.items():
        if city.lower() in location_str.lower():
            return coords
    return (0.0, 0.0)


def _parse_salary(salary_str: str):
    """Parse '$120K-$180K', '£70K-£130K', '€65K-€110K', 'CAD$100K-CAD$160K' → (low, high, currency)."""
    currency = "USD"
    for symbol, code in _SALARY_CURRENCY_MAP:
        if symbol in salary_str:
            currency = code
            break
    try:
        cleaned = re.sub(r"[£€]|[A-Z]{2,3}\$", "", salary_str)
        cleaned = cleaned.replace("$", "").replace("K", "000")
        parts = cleaned.split("-")
        return float(parts[0].strip()), float(parts[1].strip()), currency
    except Exception:
        return 0.0, 0.0, currency


def _build_skills_tiers(required: list, nice_to_have: list) -> dict:
    """Distribute synthetic skills across all tiers for realistic demo data.

    required skills split: first 2 → must_have, next 2 → strong,
                           next 2 → experience, remainder → knowledge
    nice_to_have split:    first half → familiarity, rest → nice_to_have
    """
    tiers: dict = {}
    slots = [("must_have", 2), ("strong", 2), ("experience", 2), ("knowledge", None)]
    pos = 0
    for tier_key, count in slots:
        if pos >= len(required):
            break
        chunk = required[pos: pos + count] if count else required[pos:]
        if chunk:
            tiers[tier_key] = chunk
        pos += len(chunk)

    mid = len(nice_to_have) // 2
    if nice_to_have[:mid]:
        tiers["familiarity"] = nice_to_have[:mid]
    if nice_to_have[mid:]:
        tiers["nice_to_have"] = nice_to_have[mid:]

    return tiers


# ---------------------------------------------------------------------------
# Step 1 — Generate synthetic data
# ---------------------------------------------------------------------------

def generate_data(n_resumes: int, n_jds: int, locales: dict = None):
    print("\n[1/3] Generating synthetic data...")
    # Wipe old synthetic files so stale resumes from previous runs don't bleed in
    import shutil
    for sub in ["resumes", "job_descriptions"]:
        p = SYNTHETIC_DIR / sub
        if p.exists():
            shutil.rmtree(p)
    if (SYNTHETIC_DIR / "manifest.json").exists():
        (SYNTHETIC_DIR / "manifest.json").unlink()
    import subprocess
    cmd = [sys.executable, str(PROJECT_ROOT / "scripts" / "generate_synthetic_data.py"),
           "--resumes", str(n_resumes), "--jds", str(n_jds),
           "--quality-only", "--output", str(SYNTHETIC_DIR)]
    for locale_key, locale_n in (locales or {}).items():
        if locale_n > 0:
            cmd += ["--locale", f"{locale_key}={locale_n}"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR: {result.stderr}")
        sys.exit(1)
    for line in result.stdout.strip().splitlines():
        print(f"  {line}")
    print("  Done.")


# ---------------------------------------------------------------------------
# Step 2 — Copy resumes to raw_resumes/ as demo_<name>.<ext>
# ---------------------------------------------------------------------------

def _name_slug(json_path: Path) -> str:
    """Read contact.name from JSON and return a filesystem-safe slug."""
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        name = data.get("contact", {}).get("name", "")
        if name:
            slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
            return slug
    except Exception:
        pass
    return ""


def copy_resumes():
    print(f"\n[2/3] Copying demo resumes to {RAW_RESUMES_DIR}...")
    RAW_RESUMES_DIR.mkdir(parents=True, exist_ok=True)

    FORMATS = ["docx", "txt", "pdf"]
    copied = 0
    format_counts: dict = {}

    # Build a set of existing demo_ filenames for deduplication
    existing_names = {f.stem for f in RAW_RESUMES_DIR.iterdir() if f.name.startswith("demo_")}

    idx = 0
    for category in DEMO_RESUME_CATEGORIES:
        src_dir = SYNTHETIC_DIR / "resumes" / category
        if not src_dir.exists():
            print(f"  Warning: {src_dir} not found, skipping.")
            continue

        json_files = sorted(src_dir.glob("*.json"))
        for json_file in json_files:
            slug = _name_slug(json_file) or json_file.stem
            fmt = FORMATS[idx % len(FORMATS)]
            idx += 1

            # Deduplicate stem
            stem = f"demo_{slug}"
            if stem in existing_names:
                for n in range(2, 20):
                    candidate = f"demo_{slug}_{n}"
                    if candidate not in existing_names:
                        stem = candidate
                        break
            existing_names.add(stem)

            dest = RAW_RESUMES_DIR / f"{stem}.{fmt}"
            if dest.exists():
                continue

            # Generate in the chosen format
            try:
                resume_json = json.loads(json_file.read_text(encoding="utf-8"))
                if fmt == "txt":
                    txt_src = json_file.with_suffix(".txt")
                    if txt_src.exists():
                        shutil.copy2(txt_src, dest)
                    else:
                        dest.write_text(_json_to_text(resume_json), encoding="utf-8")
                elif fmt == "docx":
                    sys.path.insert(0, str(PROJECT_ROOT / "backend"))
                    from services.export_service import generate_docx
                    bio = generate_docx(resume_json)
                    dest.write_bytes(bio.read())
                elif fmt == "pdf":
                    _generate_pdf(resume_json, dest)
                copied += 1
                format_counts[fmt] = format_counts.get(fmt, 0) + 1
            except Exception as e:
                # Fallback to .txt
                txt_src = json_file.with_suffix(".txt")
                fallback = dest.with_suffix(".txt")
                if txt_src.exists() and not fallback.exists():
                    shutil.copy2(txt_src, fallback)
                    copied += 1
                    format_counts["txt"] = format_counts.get("txt", 0) + 1
                else:
                    print(f"  Warning: could not copy {json_file.name}: {e}")

    print(f"  Copied {copied} resume files. Formats: {format_counts}")
    return copied


def _json_to_text(data: dict) -> str:
    contact = data.get("contact", {})
    lines = [contact.get("name", ""), f"{contact.get('email','')} | {contact.get('phone','')} | {contact.get('location','')}",
             "", "PROFESSIONAL SUMMARY", data.get("summary", ""), "", "TECHNICAL SKILLS",
             ", ".join(data.get("skills", [])), "", "EXPERIENCE"]
    for exp in data.get("experience", []):
        lines += [f"\n{exp.get('title')} | {exp.get('company')} | {exp.get('period')}"]
        lines += [f"- {b}" for b in exp.get("bullets", [])]
    lines += ["", "EDUCATION"]
    for edu in data.get("education", []):
        lines.append(f"{edu.get('degree')} | {edu.get('school')} | {edu.get('year')}")
    return "\n".join(lines)


def _generate_pdf(resume_json: dict, dest: Path):
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.units import inch
        from reportlab.lib.enums import TA_CENTER

        doc = SimpleDocTemplate(str(dest), pagesize=letter,
                                leftMargin=0.75*inch, rightMargin=0.75*inch,
                                topMargin=0.75*inch, bottomMargin=0.75*inch)
        styles = getSampleStyleSheet()
        heading_style = ParagraphStyle("Heading", parent=styles["Heading1"], fontSize=14, alignment=TA_CENTER)
        body_style = styles["Normal"]
        story = []

        contact = resume_json.get("contact", {})
        if contact.get("name"):
            story.append(Paragraph(contact["name"], heading_style))
        details = " | ".join(filter(None, [contact.get("email"), contact.get("phone"), contact.get("location")]))
        if details:
            story.append(Paragraph(details, ParagraphStyle("Center", parent=body_style, alignment=TA_CENTER)))
        story.append(Spacer(1, 0.1*inch))

        txt = _json_to_text(resume_json)
        for line in txt.splitlines():
            if line.strip():
                story.append(Paragraph(line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"), body_style))
            else:
                story.append(Spacer(1, 0.05*inch))

        doc.build(story)
    except ImportError:
        dest.with_suffix(".txt").write_text(_json_to_text(resume_json), encoding="utf-8")


# ---------------------------------------------------------------------------
# Step 3a — Index resumes into LanceDB
# ---------------------------------------------------------------------------

def _get_indexed_filenames() -> set:
    try:
        from services.db.lancedb_client import get_or_create_table
        table = get_or_create_table()
        df = table.to_pandas()
        existing = df[df["user_id"] == DEMO_USER_ID]["filename"].unique().tolist()
        return set(existing)
    except Exception:
        return set()


def _get_openrouter_key() -> str:
    # DB takes priority — key is stored encrypted under user settings
    try:
        from app.common import decrypt_value
        from services.db.lancedb_client import get_user_settings
        settings = get_user_settings(DEMO_USER_ID)
        if settings and settings.get("openRouterKey"):
            key = decrypt_value(settings["openRouterKey"])
            if key:
                print("  INFO: Using OpenRouter key from stored settings.")
                return key
    except Exception:
        pass
    # Fallback: env var (skip placeholder values)
    key = os.getenv("OPEN_ROUTER_KEY", "")
    if key and not key.startswith("your_"):
        return key
    return ""


_CATEGORY_EXP_LEVEL = {
    "junior":    "Junior",
    "mid":       "Mid-level",
    "senior":    "Senior",
    "architect": "Lead",
    "strong":    "Senior",
    "good":      "Mid-level",
}

_CATEGORY_YEARS = {
    "junior":    "1",
    "mid":       "3",
    "senior":    "7",
    "architect": "12",
    "strong":    "6",
    "good":      "3",
}

# Skill-level distribution per category — mirrors what the LLM assigns for real resumes.
# Values cycle across skills so not every skill gets the same label.
_CATEGORY_SKILL_LEVELS = {
    "junior":    ["Beginner", "Intermediate", "Beginner"],
    "mid":       ["Intermediate", "Advanced", "Intermediate"],
    "senior":    ["Advanced", "Expert", "Advanced"],
    "architect": ["Expert", "Advanced", "Expert"],
    "strong":    ["Advanced", "Expert", "Advanced"],
    "good":      ["Intermediate", "Advanced", "Intermediate"],
}


def _skills_with_levels(raw_skills: list, category: str) -> list:
    """Wrap flat skill strings with a level based on resume seniority tier.

    The resulting {name, level} dicts are passed into _clean_metadata() which
    validates level values against _VALID_LEVELS — keeping normalization in the
    API call stack while avoiding a per-resume LLM round-trip.
    """
    levels = _CATEGORY_SKILL_LEVELS.get(category, ["Intermediate"])
    result = []
    for i, s in enumerate(raw_skills):
        name = (s.get("name") if isinstance(s, dict) else str(s)).strip()
        if name:
            result.append({"name": name, "level": levels[i % len(levels)]})
    return result


def _build_raw_meta(resume_json: dict, category: str) -> dict:
    """Assemble raw (un-normalized) metadata from synthetic JSON.

    This dict is passed directly into _clean_metadata() from the resumes route,
    so all field normalization (location, phone, skills, industry, etc.) runs
    through the same API call stack as a real resume upload.
    """
    contact  = resume_json.get("contact", {})
    exp_list = resume_json.get("experience", [])
    edu_list = resume_json.get("education", [])

    edu_str = ""
    if edu_list:
        e = edu_list[0]
        parts = [e.get("degree", ""), e.get("school", ""), str(e.get("year", ""))]
        edu_str = " | ".join(p for p in parts if p)

    return {
        "candidate_name":   contact.get("name"),
        "current_company":  exp_list[0].get("company", "") if exp_list else "",
        "location":         contact.get("location"),
        "phone":            contact.get("phone"),
        "email":            contact.get("email"),
        "linkedin_url":     contact.get("linkedin"),
        "github_url":       contact.get("github"),
        "industry":         INDUSTRY_DISPLAY.get(resume_json.get("industry", ""), None),
        "role":             exp_list[0].get("title", "") if exp_list else "",
        "exp_level":        _CATEGORY_EXP_LEVEL.get(category),
        "skills":           _skills_with_levels(resume_json.get("skills", []), category),
        "summary":          resume_json.get("summary"),
        "years_experience": _CATEGORY_YEARS.get(category),
        "education":        edu_str or None,
        "certifications":   resume_json.get("certifications", []),
    }


def index_resumes():
    """Index resume vectors and populate resume_meta in one pass per file."""
    print(f"\n[3a/3] Indexing resumes + metadata (user={DEMO_USER_ID})...")
    from services.db.lancedb_client import store_resume, store_resume_validation
    from services.resume_parser import extract_text
    from app.routes.v1.resumes import _clean_metadata

    api_key = _get_openrouter_key()
    if not api_key:
        print("  WARNING: OPEN_ROUTER_KEY not set — embeddings will use zero vectors.")

    already_indexed = _get_indexed_filenames()
    if already_indexed:
        print(f"  Found {len(already_indexed)} already-indexed demo resume(s) — will skip those.")

    # Build slug→(file_path, json_path, category) mapping from synthetic JSON
    resume_map: dict = {}   # filename → (file_path, json_file, category)
    used_names: set  = set()
    idx = 0
    FORMATS = ["docx", "txt", "pdf"]

    for category in DEMO_RESUME_CATEGORIES:
        src_dir = SYNTHETIC_DIR / "resumes" / category
        if not src_dir.exists():
            continue
        for json_file in sorted(src_dir.glob("*.json")):
            slug = _name_slug(json_file) or json_file.stem
            fmt  = FORMATS[idx % len(FORMATS)]
            idx += 1
            stem = f"demo_{slug}"
            if stem in used_names:
                for n in range(2, 20):
                    candidate = f"demo_{slug}_{n}"
                    if candidate not in used_names:
                        stem = candidate
                        break
            used_names.add(stem)
            filename  = f"{stem}.{fmt}"
            file_path = RAW_RESUMES_DIR / filename
            if not file_path.exists():
                txt_path = RAW_RESUMES_DIR / f"{stem}.txt"
                if txt_path.exists():
                    filename  = txt_path.name
                    file_path = txt_path
                else:
                    continue
            resume_map[filename] = (file_path, json_file, category)

    total   = len(resume_map)
    success = skipped = errors = 0

    for i, (filename, (file_path, json_file, category)) in enumerate(resume_map.items(), 1):
        if filename in already_indexed:
            skipped += 1
            continue
        try:
            text = (file_path.read_text(encoding="utf-8")
                    if file_path.suffix == ".txt" else extract_text(str(file_path)))
            if not text or not text.strip():
                continue

            # 1. Store vector embeddings
            store_resume(filename, text, DEMO_USER_ID, api_key=api_key)

            # 2. Store metadata — normalize via API call stack (_clean_metadata)
            resume_json = json.loads(json_file.read_text(encoding="utf-8"))
            raw_meta = _build_raw_meta(resume_json, category)
            meta = _clean_metadata(raw_meta)
            store_resume_validation(DEMO_USER_ID, filename, {}, meta)

            success += 1
            if success % 10 == 0 or i == total:
                print(f"  [{i}/{total}] indexed {filename}")
        except Exception as e:
            errors += 1
            print(f"  ERROR indexing {filename}: {e}")

    if skipped:
        print(f"  Indexed {success} new resumes. Skipped {skipped} already in DB. Errors: {errors}.")
    else:
        print(f"  Indexed {success}/{total} resumes. Errors: {errors}.")


# ---------------------------------------------------------------------------
# Step 3b — Insert job descriptions into LanceDB jobs table
# ---------------------------------------------------------------------------

def _count_existing_demo_jobs() -> int:
    try:
        from services.db.lancedb_client import get_or_create_jobs_table
        table = get_or_create_jobs_table()
        df = table.to_pandas()
        demo_jobs = df[
            (df["user_id"] == DEMO_USER_ID) &
            (df["metadata"].str.contains('"generated": true', na=False))
        ]
        return len(demo_jobs)
    except Exception:
        return 0


def insert_jobs():
    print(f"\n[3b/3] Inserting job descriptions into jobs table (user={DEMO_USER_ID})...")
    from services.db.lancedb_client import get_or_create_jobs_table, get_embeddings_model
    from app.routes.v1.jobs import _normalize_job_fields

    existing_count = _count_existing_demo_jobs()
    if existing_count > 0:
        print(f"  {existing_count} demo job(s) already in DB — skipping insert. "
              f"Run 'make demo-wipe' to reload from scratch.")
        return

    table = get_or_create_jobs_table()

    # Mirror create_job route: init embeddings once, fall back to zero vectors on failure
    try:
        embeddings = get_embeddings_model()
        use_embeddings = True
    except Exception as e:
        print(f"  WARNING: Could not init embeddings ({e}). Jobs will use zero vectors.")
        use_embeddings = False

    manifest_path = SYNTHETIC_DIR / "manifest.json"
    with open(manifest_path) as f:
        manifest = json.load(f)

    success = 0
    errors = 0
    total = len(manifest["job_descriptions"])

    for i, entry in enumerate(manifest["job_descriptions"], 1):
        try:
            jd_txt = (SYNTHETIC_DIR / entry["file"]).read_text(encoding="utf-8")
            jd_json_path = SYNTHETIC_DIR / entry["json_file"]
            with open(jd_json_path) as f:
                jd_meta = json.load(f)

            title         = jd_meta.get("title", entry.get("title", "Software Engineer"))
            location      = jd_meta.get("location", entry.get("location", "Remote"))
            industry      = jd_meta.get("industry", "IT")
            skills        = jd_meta.get("required_skills", [])
            nice_to_have  = jd_meta.get("nice_to_have", [])
            salary_str    = jd_meta.get("salary_range", "$100K-$150K")
            employer_name = jd_meta.get("company_name", "Demo Corp")
            salary_min, salary_max, salary_currency = _parse_salary(salary_str)

            job_dict = {
                "job_id":           str(uuid.uuid4()),
                "user_id":          DEMO_USER_ID,
                "title":            title,
                "description":      jd_txt,
                "employer_name":    employer_name,
                "employer_email":   "demo@example.com",
                "location_name":    location,
                "location_lat":     0.0,
                "location_lng":     0.0,
                "employment_type":  "full_time",
                "job_category":     INDUSTRY_CATEGORY.get(industry, "IT"),
                "job_level":        _infer_level(title),
                "skills_required":  skills + nice_to_have,
                "skills_tiers":     _build_skills_tiers(skills, nice_to_have),
                "salary_min":       salary_min,
                "salary_max":       salary_max,
                "salary_currency":  salary_currency,
                "benefits":         BENEFITS,
                "application_url":  "",
                "metadata":         json.dumps({"industry": industry, "generated": True}),
                "posted_date":      datetime.now().isoformat(),
                "vector":           [0.0] * 1536,
            }

            # Run the same normalization as the create_job route
            job_dict = _normalize_job_fields(job_dict)

            # Fill in geo after normalization (uses the cleaned location_name)
            job_dict["location_lat"], job_dict["location_lng"] = _infer_geo(job_dict["location_name"])

            # Generate embedding — same logic as create_job route
            skills_text = ", ".join(job_dict.get("skills_required", []))
            embed_text  = f"{job_dict['title']}\n{jd_txt[:800]}\nSkills: {skills_text}"
            if use_embeddings:
                try:
                    job_dict["vector"] = embeddings.embed_query(embed_text)
                except Exception:
                    pass

            table.add([job_dict])
            success += 1
            if i % 10 == 0 or i == total:
                print(f"  [{i}/{total}] inserted: {title[:60]}")

        except Exception as e:
            errors += 1
            print(f"  ERROR inserting JD {i}: {e}")

    print(f"  Inserted {success}/{total} job descriptions. Errors: {errors}.")


# ---------------------------------------------------------------------------
# Wipe helper
# ---------------------------------------------------------------------------

def wipe_demo_jobs():
    """Delete only the demo-generated JDs from the jobs table (leaves resumes intact)."""
    print("  Wiping demo job descriptions...")
    try:
        from services.db.lancedb_client import get_or_create_jobs_table
        table = get_or_create_jobs_table()
        df = table.to_pandas()
        before = len(df)
        mask = (
            (df["user_id"] == DEMO_USER_ID) &
            (df["metadata"].str.contains('"generated": true', na=False))
        )
        demo_ids = df[mask]["job_id"].tolist()
        if not demo_ids:
            print("  No demo JDs found — nothing to wipe.")
            return
        for job_id in demo_ids:
            table.delete(f'job_id = "{job_id}"')
        after = len(table.to_pandas())
        print(f"  Removed {before - after} demo JD(s). {after} row(s) remain.")
    except Exception as e:
        print(f"  ERROR wiping demo JDs: {e}")
        sys.exit(1)


def wipe_demo_resumes():
    """Delete all demo resumes from resumes, resume_meta, and raw_resumes/."""
    print("  Wiping demo resumes...")
    try:
        from services.db.lancedb_client import get_or_create_table, get_or_create_resume_meta_table
        resumes_table = get_or_create_table()
        meta_table = get_or_create_resume_meta_table()

        r_df = resumes_table.to_pandas()
        demo_mask = r_df["user_id"] == DEMO_USER_ID
        removed_vectors = int(demo_mask.sum())
        if removed_vectors:
            resumes_table.delete(f"user_id = '{DEMO_USER_ID}'")

        m_df = meta_table.to_pandas()
        demo_meta = m_df[m_df["user_id"] == DEMO_USER_ID]
        removed_meta = len(demo_meta)
        if removed_meta:
            meta_table.delete(f"user_id = '{DEMO_USER_ID}'")

        # Remove demo_ files from raw_resumes/
        removed_files = 0
        if RAW_RESUMES_DIR.exists():
            for f in RAW_RESUMES_DIR.glob("demo_*"):
                f.unlink()
                removed_files += 1

        print(f"  Removed {removed_vectors} vector row(s), {removed_meta} meta row(s), "
              f"{removed_files} file(s) from raw_resumes/.")
    except Exception as e:
        print(f"  ERROR wiping demo resumes: {e}")
        sys.exit(1)


def wipe_demo_all():
    """Wipe all demo data: resumes (vectors + meta + files) and JDs."""
    print("\n[0/3] Wiping existing demo data...")
    wipe_demo_resumes()
    wipe_demo_jobs()
    print("  Wipe complete.")


def wipe_existing():
    print("\n[0/3] Wiping existing demo data...")
    import subprocess
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "wipe_database.py"),
         "--all", "--keep-settings", "--uploads", "--yes"],
        capture_output=True, text=True
    )
    for line in (result.stdout + result.stderr).strip().splitlines():
        print(f"  {line}")
    print("  Wipe complete.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    global N_RESUMES, N_JDS, N_LOCALES
    parser = argparse.ArgumentParser(description="Load demo data into Resume Intelligence DB")
    parser.add_argument("--resumes", type=int, default=N_RESUMES, help=f"Number of resumes (default: {N_RESUMES})")
    parser.add_argument("--jds", type=int, default=N_JDS, help=f"Number of job descriptions (default: {N_JDS})")
    parser.add_argument("--locale", metavar="KEY=N", action="append", default=[],
                        help="Locale-specific resume counts, e.g. --locale uk=18 --locale eu=10")
    parser.add_argument("--india", type=int, default=0,
                        help="Shorthand for --locale india=N (backward compat)")
    parser.add_argument("--skip-generate", action="store_true",
                        help="Skip synthetic data generation (reuse existing data/synthetic/)")
    parser.add_argument("--wipe", action="store_true",
                        help="Wipe existing DB and uploads before loading")
    parser.add_argument("--wipe-jds", action="store_true",
                        help="Delete only demo-generated JDs from the jobs table, then exit")
    parser.add_argument("--wipe-demo", action="store_true",
                        help="Wipe all demo data (resumes + JDs + files), then exit")
    parser.add_argument("--reset", action="store_true",
                        help="Wipe all demo data (resumes + JDs) then reload with specified counts")
    args = parser.parse_args()

    N_RESUMES = args.resumes
    N_JDS     = args.jds

    # Build locale dict from --locale KEY=N args + --india shorthand
    N_LOCALES = {}
    if args.india > 0:
        N_LOCALES["india"] = args.india
    for pair in args.locale:
        key, _, val = pair.partition("=")
        N_LOCALES[key.lower()] = N_LOCALES.get(key.lower(), 0) + int(val)

    print("=" * 60)
    print("  Resume Intelligence — Demo Data Loader")
    print("=" * 60)

    if args.wipe_jds:
        wipe_demo_jobs()
        print("\nDone.\n")
        return

    if args.wipe_demo:
        wipe_demo_all()
        print("\nDone.\n")
        return

    if args.reset:
        wipe_demo_all()
    elif args.wipe:
        wipe_existing()

    if not args.skip_generate:
        generate_data(N_RESUMES, N_JDS, N_LOCALES)
    else:
        print("\n[1/3] Skipping generation (--skip-generate).")
        if not (SYNTHETIC_DIR / "manifest.json").exists():
            print("  ERROR: data/synthetic/manifest.json not found. Run without --skip-generate first.")
            sys.exit(1)

    copy_resumes()
    index_resumes()
    insert_jobs()

    print("\n" + "=" * 60)
    print("  Demo data loaded successfully!")
    print(f"  Resumes indexed as user: {DEMO_USER_ID}")
    print(f"  Jobs inserted as user:   {DEMO_USER_ID}")
    print("  Start the app with: make dev")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
