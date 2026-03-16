#!/usr/bin/env python3
"""
Normalize location strings in resume_meta:
- Sub-neighborhood → city level  (Koramangala, Bangalore → Bangalore, India)
- Variant spellings              (Bengaluru → Bangalore)
- State clutter removed          (Pune, Maharashtra → Pune, India)

Usage:
    python scripts/fix_locations.py
    python scripts/fix_locations.py --dry-run
"""
import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

# Exact replacements — order matters (most specific first)
NORMALIZATIONS = [
    # Bangalore sub-areas → Bangalore, India
    ("Electronic City, Bangalore, India",   "Bangalore, India"),
    ("Koramangala, Bangalore, India",        "Bangalore, India"),
    ("Whitefield, Bangalore, India",         "Bangalore, India"),
    ("HSR Layout, Bangalore, India",         "Bangalore, India"),
    ("Indiranagar, Bangalore, India",        "Bangalore, India"),
    ("Bengaluru, Karnataka, India",          "Bangalore, India"),
    ("Bengaluru, India",                     "Bangalore, India"),
    # Hyderabad sub-areas
    ("Gachibowli, Hyderabad, India",         "Hyderabad, India"),
    ("Hyderabad, Telangana, India",          "Hyderabad, India"),
    # Delhi NCR
    ("Gurugram, Haryana, India",             "Gurugram, India"),
    ("Noida, UP, India",                     "Noida, India"),
    # Pune / Mumbai
    ("Pune, Maharashtra, India",             "Pune, India"),
    # London
    ("London, England",                      "London, UK"),
    # Remote variants
    ("Remote (India)",                       "Remote"),
    ("Remote — Bangalore, India",            "Remote"),
    ("Remote — Hyderabad, India",            "Remote"),
]

# Build lookup for O(1) access
_NORM_MAP = {old.strip().lower(): new for old, new in NORMALIZATIONS}


def normalize(loc: str) -> str:
    return _NORM_MAP.get(loc.strip().lower(), loc.strip())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    from services.db.lancedb_client import (
        get_or_create_resume_meta_table,
        store_resume_validation,
        list_all_resumes_with_users,
    )

    all_r = list_all_resumes_with_users()
    resume_map = {r["filename"]: r["user_id"] for r in all_r}

    table = get_or_create_resume_meta_table()
    df = table.to_pandas()

    updated = 0
    for _, row in df.iterrows():
        old_loc = str(row.get("location") or "").strip()
        if not old_loc:
            continue
        new_loc = normalize(old_loc)
        if new_loc == old_loc:
            continue

        fn = str(row["filename"])
        print(f"  {fn}")
        print(f"    '{old_loc}' → '{new_loc}'")

        if not args.dry_run:
            meta = {
                "candidate_name":  row["candidate_name"],
                "role":            row["role"],
                "industry":        row["industry"],
                "exp_level":       row["exp_level"],
                "current_company": row["current_company"],
                "location":        new_loc,
                "phone":           row["phone"],
                "email":           row["email"],
                "linkedin_url":    row["linkedin_url"],
                "github_url":      row["github_url"],
                "summary":         row["summary"],
                "years_experience":row["years_experience"],
                "education":       row["education"],
                "certifications":  json.loads(row["certifications_json"] or "[]"),
                "skills":          json.loads(row["skills_json"] or "[]"),
            }
            store_resume_validation(
                resume_map.get(fn, str(row.get("user_id", ""))),
                fn, {}, meta
            )
        updated += 1

    print(f"\n=== Done — {updated} records {'would be ' if args.dry_run else ''}updated ===")
    if args.dry_run:
        print("  (dry-run — no changes written)")


if __name__ == "__main__":
    main()
