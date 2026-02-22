import streamlit as st
from services.agent_controller import run_resume_pipeline

st.set_page_config(layout="wide")
st.header("🧠 Skill Gap Analysis (LangGraph Powered)")

col1, col2 = st.columns(2)

with col1:
    resume_text = st.text_area(
        "📄 Candidate Resume",
        height=300,
        placeholder="Paste resume text here..."
    )

with col2:
    jd_text = st.text_area(
        "📋 Job Description",
        height=300,
        placeholder="Paste job description here..."
    )

if st.button("🔍 Analyze Skill Gaps"):
    if not resume_text.strip() or not jd_text.strip():
        st.warning("Please provide both resume and job description")
    else:
        with st.spinner("Running skill gap agent..."):
            output = run_resume_pipeline(
                task="skill_gap",
                resumes=[resume_text],
                query=jd_text
            )

        gaps = output["gaps"]

        st.subheader("🚫 Missing Skills")
        for skill in gaps["missing_skills"]:
            st.error(skill)

        st.subheader("📚 Recommended Skills to Learn")
        for skill in gaps["recommended"]:
            st.success(skill)
