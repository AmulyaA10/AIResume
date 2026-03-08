#!/usr/bin/env python3
"""
Wipe the LanceDB database and optionally the uploaded files.

Usage:
    python scripts/wipe_database.py              # wipe resume tables only
    python scripts/wipe_database.py --all        # wipe all tables
    python scripts/wipe_database.py --uploads    # also delete uploaded files
    python scripts/wipe_database.py --all --uploads  # full reset
"""

import argparse
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "lancedb"
UPLOADS_PATH = PROJECT_ROOT / "data" / "raw_resumes"

RESUME_TABLES = [
    "resumes.lance",
    "resume_meta.lance",
    "activity.lance",
    "job_resume_applied.lance",
]

ALL_TABLES = RESUME_TABLES + [
    "jobs.lance",
    "user_settings.lance",
]


def wipe_tables(tables: list[str], dry_run: bool = False) -> None:
    for table in tables:
        path = DB_PATH / table
        if path.exists():
            print(f"  Deleting {path}")
            if not dry_run:
                shutil.rmtree(path)
        else:
            print(f"  Skipping {path} (not found)")


def wipe_uploads(dry_run: bool = False) -> None:
    if not UPLOADS_PATH.exists():
        print(f"  Uploads directory not found: {UPLOADS_PATH}")
        return
    files = list(UPLOADS_PATH.iterdir())
    if not files:
        print("  Uploads directory is already empty.")
        return
    for f in files:
        print(f"  Deleting {f.name}")
        if not dry_run:
            f.unlink() if f.is_file() else shutil.rmtree(f)


def confirm(prompt: str) -> bool:
    answer = input(f"{prompt} [y/N]: ").strip().lower()
    return answer == "y"


def main() -> None:
    parser = argparse.ArgumentParser(description="Wipe AIResume database tables and/or uploads.")
    parser.add_argument("--all", action="store_true", help="Wipe all tables (including jobs and user settings)")
    parser.add_argument("--uploads", action="store_true", help="Also delete uploaded files in data/uploads/")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    tables = ALL_TABLES if args.all else RESUME_TABLES
    scope = "ALL tables" if args.all else "resume tables (resumes, resume_meta, activity, job_resume_applied)"

    print(f"\nScope: {scope}")
    if args.uploads:
        print("       + uploaded files")
    print()

    if not args.yes and not confirm("This is irreversible. Continue?"):
        print("Aborted.")
        sys.exit(0)

    print("\nWiping database tables...")
    wipe_tables(tables)

    if args.uploads:
        print("\nWiping uploaded files...")
        wipe_uploads()

    print("\nDone. The backend will recreate tables automatically on next startup.")


if __name__ == "__main__":
    main()
