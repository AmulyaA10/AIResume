#!/usr/bin/env python3
"""
Fix phone numbers in resume_meta:
- Extract phones from resume text using robust regex
- Detect extensions (ext. 1234)
- Infer country code from candidate location if not already international
- Update DB in-place (no LLM cost)

Usage:
    python scripts/fix_phone_numbers.py
    python scripts/fix_phone_numbers.py --dry-run
"""
import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

# ---------------------------------------------------------------------------
# Country code lookup by country/state keyword in location string
# ---------------------------------------------------------------------------
COUNTRY_CODES = {
    # Country name fragments → dial code
    "united kingdom": "+44", "uk": "+44", "england": "+44", "scotland": "+44", "wales": "+44",
    "india": "+91",
    "australia": "+61",
    "canada": "+1",
    "germany": "+49",
    "france": "+33",
    "netherlands": "+31",
    "singapore": "+65",
    "new zealand": "+64",
    "ireland": "+353",
    "pakistan": "+92",
    "nigeria": "+234",
    "kenya": "+254",
    "south africa": "+27",
    "brazil": "+55",
    "mexico": "+52",
    "uae": "+971", "dubai": "+971",
    "philippines": "+63",
    "bangladesh": "+880",
    "sri lanka": "+94",
    "malaysia": "+60",
}

# US state abbreviations — if location looks US, default +1
US_STATES = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
    "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
    "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
    "VA","WA","WV","WI","WY","DC",
}


def infer_country_code(location: str) -> str:
    """Return dial code like '+1', '+44' based on location string, or '' if unknown."""
    if not location:
        return "+1"  # default US
    loc = location.strip().lower()
    for keyword, code in COUNTRY_CODES.items():
        if keyword in loc:
            return code
    # Check for US state abbreviation: "Seattle, WA" → WA
    parts = [p.strip().upper() for p in loc.split(",")]
    if any(p in US_STATES for p in parts):
        return "+1"
    return "+1"  # safe default


def format_phone(raw: str, country_code: str, ext: str = "") -> str:
    """Format a phone number string into a clean, readable format."""
    # Extract inline x-extension (e.g. '212.308.2677x3454' → ext='3454')
    inline_ext = re.search(r'x(\d{2,6})$', raw.strip(), re.IGNORECASE)
    if inline_ext and not ext:
        ext = inline_ext.group(1)
        raw = raw[:inline_ext.start()].strip()

    ext_suffix = f" ext. {ext}" if ext else ""
    d = re.sub(r"\D", "", raw)

    if len(d) == 10:
        formatted = f"{country_code} ({d[:3]}) {d[3:6]}-{d[6:]}"
    elif len(d) == 11 and d[0] == "1":
        formatted = f"+1 ({d[1:4]}) {d[4:7]}-{d[7:]}"
    elif len(d) >= 7 and raw.startswith("+"):
        # Already has country code — reformat if possible
        formatted = raw.strip()
    elif len(d) >= 7:
        formatted = f"{country_code} {raw.strip()}"
    else:
        return ""
    return formatted + ext_suffix


# ---------------------------------------------------------------------------
# Phone extraction from text
# ---------------------------------------------------------------------------
# Pattern 1: labeled — "Phone: ...", "Mobile: ...", "Tel: ..."
RE_LABELED = re.compile(
    r'(?:phone|mobile|cell|tel|ph|contact\s*no)[:\s#]*'
    r'(\+?[\d\s\-\.\(\)\/]{7,30}(?:\s*(?:ext?|x)\.?\s*\d{2,6})?)',
    re.IGNORECASE,
)
# Pattern 2: international format +CC ...
RE_INTL = re.compile(
    r'(\+\d{1,3}[\s\-\.]?\(?\d{1,4}\)?[\s\-\.]?\d{2,5}[\s\-\.]?\d{2,5}'
    r'(?:[\s\-\.]\d{2,5})?(?:\s*(?:ext?|x)\.?\s*\d{2,6})?)'
)
# Pattern 3: North American (XXX) XXX-XXXX or XXX.XXX.XXXX or XXX-XXX-XXXX
RE_NA = re.compile(
    r'(\(?\d{3}\)?[\s\-\.]\d{3}[\s\-\.]\d{4}(?:\s*(?:ext?|x)\.?\s*\d{2,6})?)'
)
RE_EXT = re.compile(r'(?:[eE]xt?\.?\s*|(?<=\d)x)(\d{2,6})')


def extract_phone_from_text(text: str) -> tuple[str, str]:
    """Return (raw_number, extension) from resume text, or ('', '')."""
    snippet = text[:5000]  # first 5000 chars covers header section
    for pattern in (RE_LABELED, RE_INTL, RE_NA):
        m = pattern.search(snippet)
        if m:
            raw = m.group(1).strip()
            ext_m = RE_EXT.search(raw)
            ext = ext_m.group(1) if ext_m else ""
            if ext_m:
                raw = raw[:ext_m.start()].strip()
            digits = re.sub(r"\D", "", raw)
            if len(digits) >= 7:
                return raw, ext
    return "", ""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print changes without saving")
    args = parser.parse_args()

    from services.db.lancedb_client import (
        get_or_create_resume_meta_table,
        store_resume_validation,
        list_all_resumes_with_users,
        get_resume_text_map,
    )

    all_r = list_all_resumes_with_users()
    fns = [r["filename"] for r in all_r]
    resume_map = {r["filename"]: r["user_id"] for r in all_r}

    print(f"Loading texts for {len(fns)} resumes...")
    text_map = get_resume_text_map(fns)

    table = get_or_create_resume_meta_table()
    df = table.to_pandas()
    meta_by_file = {row["filename"]: row for _, row in df.iterrows()}

    updated = 0
    skipped_has_phone = 0
    skipped_no_phone = 0

    for fn in fns:
        row = meta_by_file.get(fn)
        if row is None:
            continue

        text = text_map.get(fn, "")
        raw, ext = extract_phone_from_text(text)

        if not raw:
            skipped_no_phone += 1
            continue

        location = str(row.get("location") or "")
        country_code = infer_country_code(location)

        # If raw already starts with +, don't prepend country code
        if raw.startswith("+"):
            digits = re.sub(r"\D", "", raw)
            formatted = format_phone(raw, country_code, ext)
        else:
            formatted = format_phone(raw, country_code, ext)

        existing = str(row.get("phone") or "").strip()

        if existing and existing == formatted:
            skipped_has_phone += 1
            continue

        action = "UPDATE" if existing else "NEW"
        print(f"  [{action}] {fn}")
        print(f"    location: {location} → code: {country_code}")
        print(f"    raw: '{raw}' ext: '{ext}' → '{formatted}'")
        if existing:
            print(f"    was: '{existing}'")

        if not args.dry_run:
            meta = {
                "candidate_name": row["candidate_name"],
                "role": row["role"],
                "industry": row["industry"],
                "exp_level": row["exp_level"],
                "current_company": row["current_company"],
                "location": row["location"],
                "phone": formatted,
                "email": row["email"],
                "linkedin_url": row["linkedin_url"],
                "github_url": row["github_url"],
                "summary": row["summary"],
                "years_experience": row["years_experience"],
                "education": row["education"],
                "certifications": json.loads(row["certifications_json"] or "[]"),
                "skills": json.loads(row["skills_json"] or "[]"),
            }
            store_resume_validation(resume_map[fn], fn, {}, meta)
        updated += 1

    # ------------------------------------------------------------------
    # Secondary pass: fix any existing DB phones that lack country code
    # e.g. "(498) 205-0097" → "+1 (498) 205-0097" for US locations
    # ------------------------------------------------------------------
    print("\n--- Fixing country codes on existing phones without prefix ---")
    cc_fixed = 0
    df2 = get_or_create_resume_meta_table().to_pandas()
    for _, row in df2.iterrows():
        phone = str(row.get("phone") or "").strip()
        if not phone or phone.startswith("+"):
            continue  # already has country code or no phone
        location = str(row.get("location") or "")
        country_code = infer_country_code(location)
        digits = re.sub(r"\D", "", phone.split("ext")[0].split("x")[0])
        if len(digits) == 10:
            # Extract any existing ext suffix
            ext_m = re.search(r'ext\.\s*(\d+)', phone)
            ext = ext_m.group(1) if ext_m else ""
            ext_suffix = f" ext. {ext}" if ext else ""
            new_phone = f"{country_code} ({digits[:3]}) {digits[3:6]}-{digits[6:]}{ext_suffix}"
            fn = row["filename"]
            print(f"  {fn}: '{phone}' → '{new_phone}'")
            if not args.dry_run:
                meta = {
                    "candidate_name": row["candidate_name"], "role": row["role"],
                    "industry": row["industry"], "exp_level": row["exp_level"],
                    "current_company": row["current_company"], "location": row["location"],
                    "phone": new_phone, "email": row["email"],
                    "linkedin_url": row["linkedin_url"], "github_url": row["github_url"],
                    "summary": row["summary"], "years_experience": row["years_experience"],
                    "education": row["education"],
                    "certifications": json.loads(row["certifications_json"] or "[]"),
                    "skills": json.loads(row["skills_json"] or "[]"),
                }
                store_resume_validation(resume_map.get(fn, row["user_id"]), fn, {}, meta)
            cc_fixed += 1

    print(f"\n=== Done ===")
    print(f"  Regex extracted: {updated}")
    print(f"  CC prefix fixed: {cc_fixed}")
    print(f"  No phone found:  {skipped_no_phone}")
    print(f"  Already correct: {skipped_has_phone}")
    if args.dry_run:
        print("  (dry-run — no changes written)")


if __name__ == "__main__":
    main()
