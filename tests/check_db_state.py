import lancedb
from pathlib import Path
import pandas as pd

DB_PATH = Path("data/lancedb")

def check_db():
    if not DB_PATH.exists():
        print(f"Error: DB path {DB_PATH} does not exist.")
        return

    db = lancedb.connect(DB_PATH)
    if "resumes" not in db.table_names():
        print("Error: 'resumes' table not found in database.")
        return

    table = db.open_table("resumes")
    print(f"Total rows in 'resumes' table: {len(table)}")
    
    if len(table) > 0:
        df = table.to_pandas()
        print("\nSchema Columns:")
        print(df.columns.tolist())
        
        print("\nSample Data (first 2 rows):")
        print(df.head(2))
        
        # Check if vectors are present and what their dimensions are
        if 'vector' in df.columns:
            sample_vector = df.iloc[0]['vector']
            print(f"\nVector length: {len(sample_vector)}")
        else:
            print("\nWARNING: 'vector' column missing!")

if __name__ == "__main__":
    check_db()
