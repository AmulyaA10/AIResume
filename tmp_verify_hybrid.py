
import os
import sys
from pathlib import Path

# Add project root and backend to sys.path
root = Path(__file__).resolve().parent
sys.path.append(str(root))
sys.path.append(str(root / "backend"))

from services.db.lancedb_client import get_embeddings_model, get_or_create_jobs_table
from app.routes.v1.match import search_jobs
from app.routes.v1.jobs import _serialize_job
import asyncio

async def test_hybrid_search():
    print("Testing Hybrid Search with keyword 'Python'...")
    try:
        results = await search_jobs(q="Python", limit=5, user_id="system")
        print(f"Found {len(results)} results for 'Python'")
        for i, r in enumerate(results):
            print(f"{i+1}. Score: {r['score']:.4f} | Title: {r['job']['title']} | Skills: {r['job']['skills_required']}")
    except Exception as e:
        print(f"Error testing Python: {e}")

    print("\nTesting Hybrid Search with keyword 'Backend'...")
    try:
        results = await search_jobs(q="Backend", limit=5, user_id="system")
        print(f"Found {len(results)} results for 'Backend'")
        for i, r in enumerate(results):
            print(f"{i+1}. Score: {r['score']:.4f} | Title: {r['job']['title']}")
    except Exception as e:
        print(f"Error testing Backend: {e}")

    print("\nTesting Hybrid Search with multi-word 'Senior React'...")
    try:
        results = await search_jobs(q="Senior React", limit=5, user_id="system")
        print(f"Found {len(results)} results for 'Senior React'")
        for i, r in enumerate(results):
            print(f"{i+1}. Score: {r['score']:.4f} | Title: {r['job']['title']}")
    except Exception as e:
        print(f"Error testing Senior React: {e}")

if __name__ == "__main__":
    asyncio.run(test_hybrid_search())
