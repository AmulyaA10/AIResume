
import lancedb
import os
import numpy as np

def check_db():
    db_path = "data/lancedb"
    if not os.path.exists(db_path):
        print(f"Database path {db_path} does not exist.")
        return

    db = lancedb.connect(db_path)
    table_names = db.table_names()
    
    if "jobs" in table_names:
        jobs_table = db.open_table("jobs")
        count = len(jobs_table)
        print(f"\nJobs count: {count}")
        if count > 0:
            sample = jobs_table.search().limit(10).to_list()
            zero_vectors = 0
            for i, r in enumerate(sample):
                vec = r.get("vector")
                if vec is None:
                    print(f"Job {i}: Vector is MISSING")
                    zero_vectors += 1
                else:
                    norm = np.linalg.norm(vec)
                    if norm < 0.001:
                        print(f"Job {i}: Vector is ZERO (norm={norm})")
                        zero_vectors += 1
                    else:
                        print(f"Job {i}: Vector OK (norm={norm:.4f})")
            print(f"Zero/Missing vectors in sample: {zero_vectors}/10")
    else:
        print("\n'jobs' table not found.")

    if "resumes" in table_names:
        resumes_table = db.open_table("resumes")
        count = len(resumes_table)
        print(f"\nResumes count: {count}")
        if count > 0:
            sample = resumes_table.search().limit(10).to_list()
            zero_vectors = 0
            for i, r in enumerate(sample):
                vec = r.get("vector")
                if vec is None:
                    print(f"Resume {i}: Vector is MISSING")
                    zero_vectors += 1
                else:
                    norm = np.linalg.norm(vec)
                    if norm < 0.001:
                        print(f"Resume {i}: Vector is ZERO (norm={norm})")
                        zero_vectors += 1
                    else:
                        print(f"Resume {i}: Vector OK (norm={norm:.4f})")
            print(f"Zero/Missing vectors in sample: {zero_vectors}/10")

if __name__ == "__main__":
    check_db()
