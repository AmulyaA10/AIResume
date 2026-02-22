import os
import json
import streamlit as st
from dotenv import load_dotenv

# -----------------------------
# LangChain 1.x imports
# -----------------------------
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

# -----------------------------
# DB
# -----------------------------
from services.db.lancedb_client import get_or_create_table

# -----------------------------
# Config
# -----------------------------
load_dotenv()

RESUME_DIR = "data/raw_resumes"

st.set_page_config(page_title="🔍 Search Resumes", layout="wide")
st.title("🔍 Resume Search (LLM Powered)")

# -----------------------------
# Load resumes from LanceDB
# -----------------------------
table = get_or_create_table()
df = table.to_pandas()

if df.empty:
    st.warning("No resumes found. Please upload resumes first.")
    st.stop()

# -----------------------------
# User input
# -----------------------------
query = st.text_input(
    "Search resumes (skills, role, name, experience)",
    placeholder="e.g. DevOps Engineer with AWS and CI/CD"
)

if not query:
    st.stop()

# -----------------------------
# Prepare resume text for LLM
# -----------------------------
resumes_text = ""
for _, row in df.iterrows():
    resumes_text += f"""
Filename: {row['filename']}
Resume:
{row['text']}
--------------------
"""
def skill_gap_agent(state):
    resume = set(state["normalized_resume_skills"])
    required = set(state["normalized_required_skills"])

    return {
        "gaps": {
            "missing_skills": list(required - resume),
            "matched_skills": list(required & resume)
        }
    }


# -----------------------------
# Prompt (STRICT JSON)
# -----------------------------
prompt = PromptTemplate(
    input_variables=["resumes", "query"],
    template="""
You are an AI recruiter.

Below are multiple resumes.
{resumes}

User query:
{query}

TASK:
- Identify resumes relevant to the query
- Return ONLY valid JSON (no markdown, no explanation)

FORMAT:
{{
  "results": [
    {{
      "filename": "Document4.docx",
      "score": 85,
      "justification": "2–4 sentences explaining skills, experience, and why this resume matches the query.",
      "missing_skills": ["Kubernetes", "Terraform"],
      "auto_screen": "Selected"
    }}
  ]
}}

If no resumes match:
{{
  "results": []
}}
"""
)

# -----------------------------
# LLM (Low cost + supported)
# -----------------------------
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
    api_key=os.getenv("OPEN_ROUTER_KEY"),
    base_url="https://openrouter.ai/api/v1"
)

chain = prompt | llm | StrOutputParser()

# -----------------------------
# Run search
# -----------------------------
with st.spinner("🔍 Searching resumes using AI reasoning..."):
    raw_result = chain.invoke(
        {
            "resumes": resumes_text,
            "query": query
        }
    )

# -----------------------------
# Parse output
# -----------------------------
st.subheader("📄 Search Results")

try:
    parsed = json.loads(raw_result)
except json.JSONDecodeError:
    st.error("❌ Failed to parse LLM output")
    st.text(raw_result)
    st.stop()

results = parsed.get("results", [])

if not results:
    st.info("No matching resumes found.")
    st.stop()

# -----------------------------
# Render results with download
# -----------------------------
for item in results:
    filename = item["filename"]
    justification = item["justification"]
    score = item.get("score", 0)
    missing_skills = item.get("missing_skills", [])
    decision = item.get("auto_screen", "Rejected")

    file_path = os.path.join(RESUME_DIR, filename)

    st.markdown(f"### 📄 {filename}")
    st.write(justification)

    # ---- Metrics Row ----
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Match Score", f"{score}/100")

    with col2:
        if missing_skills:
            st.write("**Skill Gaps:**")
            for skill in missing_skills:
                st.write(f"- {skill}")
        else:
            st.write("**Skill Gaps:** None")

    with col3:
        if decision.lower() == "selected":
            st.success("✅ Auto Screen: Selected")
        else:
            st.error("❌ Auto Screen: Rejected")

    # ---- Download ----
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            st.download_button(
                label="⬇️ Download Resume",
                data=f,
                file_name=filename,
                mime="application/octet-stream",
                key=filename
            )
    else:
        st.warning("⚠️ Resume file not found on server")

    st.divider()
