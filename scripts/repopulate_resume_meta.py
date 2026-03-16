#!/usr/bin/env python3
"""
Wipe resume_meta and repopulate it from scratch using LLM + regex extraction.

Usage (from project root):
    python scripts/repopulate_resume_meta.py
    python scripts/repopulate_resume_meta.py --batch 5   # smaller batches
    python scripts/repopulate_resume_meta.py --yes        # skip confirmation

Requires the backend to be stopped so LanceDB files aren't locked.
"""

import argparse
import json
import re
import sys
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

DB_PATH = PROJECT_ROOT / "data" / "lancedb"
META_TABLE_DIR = DB_PATH / "resume_meta.lance"

# ---------------------------------------------------------------------------
# Phone regex — international + North American
# ---------------------------------------------------------------------------
_RE_PHONE = re.compile(
    r'(?<!\d)'
    r'('
    r'\+\d{1,3}[\s\-\.]?\(?\d{1,4}\)?[\s\-\.]?\d{2,5}[\s\-\.]?\d{2,5}(?:[\s\-\.]\d{2,5})?'
    r'|'
    r'(\+?1[\s\-\.]?)?\(?\d{3}\)?[\s\-\.]?\d{3}[\s\-\.]?\d{4}'
    r')'
    r'(?!\d)'
)


def confirm(prompt: str) -> bool:
    return input(f"{prompt} [y/N]: ").strip().lower() == "y"


def extract_phone_regex(text: str) -> str | None:
    m = _RE_PHONE.search(text[:3000])
    if m:
        raw = m.group(0).strip()
        if re.search(r'\d{7,}', raw.replace(" ", "")):
            return raw
    return None


def main():
    parser = argparse.ArgumentParser(description="Wipe and repopulate resume_meta from LLM.")
    parser.add_argument("--batch", type=int, default=8, help="LLM batch size (default 8)")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")
    args = parser.parse_args()

    print("\n=== Resume Meta Repopulate ===")
    print(f"  Will wipe: {META_TABLE_DIR}")
    print(f"  LLM batch size: {args.batch}")
    print()

    if not args.yes and not confirm("This will wipe resume_meta and re-extract all metadata. Continue?"):
        print("Aborted.")
        sys.exit(0)

    # ------------------------------------------------------------------
    # Imports (after path setup)
    # ------------------------------------------------------------------
    from services.db.lancedb_client import (
        get_or_create_resume_meta_table,
        store_resume_validation,
        get_user_settings,
        list_all_resumes_with_users,
        get_resume_text_map,
        db as lancedb_conn,
    )
    from app.common import build_llm_config, decrypt_value
    from app.routes.v1.resumes import _llm_classify_batch, _clean_metadata

    # ------------------------------------------------------------------
    # Resolve LLM key
    # ------------------------------------------------------------------
    stored = get_user_settings("user_manager_789")
    encrypted_key = stored.get("openRouterKey") if stored else None
    if not encrypted_key:
        print("ERROR: No OpenRouter key found in user_manager_789 settings.")
        sys.exit(1)
    llm_config = build_llm_config(decrypt_value(encrypted_key), None)
    print("LLM key resolved.\n")

    # ------------------------------------------------------------------
    # Wipe resume_meta table
    # ------------------------------------------------------------------
    print("Wiping resume_meta table...", end=" ", flush=True)
    if META_TABLE_DIR.exists():
        shutil.rmtree(META_TABLE_DIR)
        print("done.")
    else:
        print("not found (will create fresh).")

    # Recreate empty table with correct schema
    get_or_create_resume_meta_table()
    print("Empty resume_meta table created.\n")

    # ------------------------------------------------------------------
    # Load all resumes
    # ------------------------------------------------------------------
    print("Loading resume list...", end=" ", flush=True)
    all_resumes = list_all_resumes_with_users()
    if not all_resumes:
        print("No resumes found in the resumes table. Exiting.")
        sys.exit(0)
    resume_map = {r["filename"]: r["user_id"] for r in all_resumes}
    print(f"{len(resume_map)} resumes found.")

    filenames = list(resume_map.keys())
    print("Loading resume texts...", end=" ", flush=True)
    text_map = get_resume_text_map(filenames)
    print(f"{len(text_map)} texts loaded.\n")

    rows = [(fn, text_map.get(fn, "")) for fn in filenames]

    # ------------------------------------------------------------------
    # Process in batches
    # ------------------------------------------------------------------
    BATCH = args.batch
    total = len(rows)
    stored_count = 0
    stats = {
        "name": 0, "phone": 0, "email": 0, "linkedin": 0, "github": 0,
        "summary": 0, "years_exp": 0, "education": 0, "certs": 0, "skills": 0,
        "phone_regex_fallback": 0,
    }

    for i in range(0, total, BATCH):
        chunk = [(fn, txt) for fn, txt in rows[i:i + BATCH] if txt.strip()]
        if not chunk:
            continue

        batch_num = i // BATCH + 1
        total_batches = (total + BATCH - 1) // BATCH
        print(f"Batch {batch_num}/{total_batches} — {[fn for fn, _ in chunk]}")

        chunk_text = {fn: txt for fn, txt in chunk}

        try:
            results = _llm_classify_batch(chunk, llm_config)
        except Exception as e:
            print(f"  ERROR in LLM call: {e} — skipping batch")
            continue

        for fn, meta in results.items():
            uid = resume_map.get(fn, "")
            if not uid:
                continue

            cleaned = _clean_metadata(meta)

            # Regex phone fallback
            if not cleaned.get("phone"):
                phone_regex = extract_phone_regex(chunk_text.get(fn, ""))
                if phone_regex:
                    cleaned["phone"] = phone_regex
                    stats["phone_regex_fallback"] += 1

            store_resume_validation(uid, fn, {}, cleaned)
            stored_count += 1

            # Update stats
            if cleaned.get("candidate_name"):   stats["name"] += 1
            if cleaned.get("phone"):             stats["phone"] += 1
            if cleaned.get("email"):             stats["email"] += 1
            if cleaned.get("linkedin_url"):      stats["linkedin"] += 1
            if cleaned.get("github_url"):        stats["github"] += 1
            if cleaned.get("summary"):           stats["summary"] += 1
            if cleaned.get("years_experience"):  stats["years_exp"] += 1
            if cleaned.get("education"):         stats["education"] += 1
            if cleaned.get("certifications"):    stats["certs"] += 1
            if cleaned.get("skills"):            stats["skills"] += 1

            print(f"  ✓ {fn}")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print(f"\n=== Done — {stored_count}/{total} resumes stored ===")
    print(f"  candidate_name:   {stats['name']}")
    print(f"  phone:            {stats['phone']}  (regex fallback: {stats['phone_regex_fallback']})")
    print(f"  email:            {stats['email']}")
    print(f"  linkedin:         {stats['linkedin']}")
    print(f"  github:           {stats['github']}")
    print(f"  summary:          {stats['summary']}")
    print(f"  years_experience: {stats['years_exp']}")
    print(f"  education:        {stats['education']}")
    print(f"  certifications:   {stats['certs']}")
    print(f"  skills:           {stats['skills']}")


if __name__ == "__main__":
    main()
