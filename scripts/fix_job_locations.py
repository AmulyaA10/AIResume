#!/usr/bin/env python3
"""
Normalize location_name strings in the jobs table using the same
_normalize_location function used for resume metadata.

Usage:
    python scripts/fix_job_locations.py
    python scripts/fix_job_locations.py --dry-run
"""
import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    from app.routes.v1.resumes import _normalize_location
    from services.db.lancedb_client import get_or_create_jobs_table

    table = get_or_create_jobs_table()
    df = table.to_pandas()

    updated = 0
    for _, row in df.iterrows():
        old_loc = str(row.get("location_name") or "").strip()
        if not old_loc:
            continue
        new_loc = _normalize_location(old_loc)
        if not new_loc or new_loc == old_loc:
            continue

        print(f"  {row['job_id']}  |  {row.get('title', '')}")
        print(f"    '{old_loc}' → '{new_loc}'")

        if not args.dry_run:
            table.update(
                where=f"job_id = '{row['job_id']}'",
                values={"location_name": new_loc},
            )
        updated += 1

    print(f"\n=== Done — {updated} records {'would be ' if args.dry_run else ''}updated ===")
    if args.dry_run:
        print("  (dry-run — no changes written)")


if __name__ == "__main__":
    main()
