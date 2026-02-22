import os
import sys
import json
from dotenv import load_dotenv

# Add root to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

from services.db.lancedb_client import store_resume, search_resumes_semantic, db

def verify_semantic_search():
    print("--- Verifying Semantic Search ---")
    
    # 1. Reset the table for testing (optional but recommended for schema changes)
    if "resumes" in db.table_names():
        print("Dropping existing resumes table to apply new schema...")
        db.drop_table("resumes")
    
    # 2. Add sample resumes
    resumes = [
        ("react_dev.txt", "Senior React Developer with experience in TypeScript, Redux, and Tailwind CSS."),
        ("python_dev.txt", "Backend Engineer specializing in Python, FastAPI, and PostgreSQL. Experience with LangChain."),
        ("ui_designer.txt", "Creative UI/UX Designer proficient in Figma, Adobe XD, and user research.")
    ]
    
    print("Indexing sample resumes...")
    for filename, text in resumes:
        print(f"Indexing {filename}...")
        store_resume(filename, text)
    
    # 3. Perform search
    query = "Looking for a Python backend developer"
    print(f"\nSearching for: '{query}'")
    results = search_resumes_semantic(query, limit=2)
    
    print("\nSearch Results:")
    print(results[['filename', 'text']])
    
    # 4. Verify ranking
    if not results.empty and results.iloc[0]['filename'] == "python_dev.txt":
        print("\n✅ SUCCESS: Python resume ranked highest for Python query.")
    else:
        print("\n❌ FAILURE: Python resume not found or not ranked highest.")

if __name__ == "__main__":
    try:
        verify_semantic_search()
    except Exception as e:
        print(f"Error during verification: {e}")
        import traceback
        traceback.print_exc()
