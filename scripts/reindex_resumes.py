import os
import sys
from dotenv import load_dotenv

# Add root to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

from services.db.lancedb_client import store_resume, db, get_or_create_table
from services.resume_parser import extract_text

RESUME_DIR = "data/raw_resumes"

def reindex_all():
    print("--- Re-indexing All Resumes ---")
    
    if not os.path.exists(RESUME_DIR):
        print(f"Error: {RESUME_DIR} not found.")
        return

    # Check for API key
    if not os.getenv("OPEN_ROUTER_KEY"):
        print("ERROR: OPEN_ROUTER_KEY not found in environment or .env file.")
        print("Please set it first before running this script.")
        return

    # Reset table if needed or just add to it
    # For a clean start with the new schema, we might want to drop it
    if "resumes" in db.list_tables():
        print("Table 'resumes' exists. Keeping it and adding new entries.")
        # table = db.open_table("resumes")
    else:
        print("Table 'resumes' does not exist. It will be created during first store.")

    files = [f for f in os.listdir(RESUME_DIR) if f.endswith(('.pdf', '.docx', '.txt'))]
    print(f"Found {len(files)} resumes to index.")

    success_count = 0
    error_count = 0

    for filename in files:
        file_path = os.path.join(RESUME_DIR, filename)
        try:
            print(f"Indexing {filename}...")
            text = extract_text(file_path)
            if not text:
                print(f"  Warning: No text extracted from {filename}")
                continue
                
            store_resume(filename, text)
            success_count += 1
            print(f"  Successfully indexed {filename}")
        except Exception as e:
            error_count += 1
            print(f"  Error indexing {filename}: {e}")

    print(f"\nRe-indexing Complete!")
    print(f"Success: {success_count}")
    print(f"Errors: {error_count}")

if __name__ == "__main__":
    reindex_all()
