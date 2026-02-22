import streamlit as st
import os
from services.resume_parser import extract_text
from services.db.lancedb_client import store_resume

UPLOAD_DIR = "data/raw_resumes"
os.makedirs(UPLOAD_DIR, exist_ok=True)

st.header("📂 Upload Resumes")

files = st.file_uploader(
    "Upload resumes (PDF / DOCX)",
    type=["pdf", "docx"],
    accept_multiple_files=True
)

store_db = st.checkbox("Store in Vector Database (LanceDB)", value=True)

if st.button("🚀 Process Resumes"):
    if not files:
        st.warning("Please upload at least one resume")
    else:
        for file in files:
            file_path = os.path.join(UPLOAD_DIR, file.name)

            # 🔽 SAVE FILE
            with open(file_path, "wb") as f:
                f.write(file.getbuffer())

                text = extract_text(file_path)
                

                if store_db:
                 store_resume(file.name, text)

            st.success(f"{file.name} saved successfully")

        st.info("All resumes stored locally")
        st.success(f"{file.name} indexed successfully")

        

