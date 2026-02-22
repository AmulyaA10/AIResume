import streamlit as st
from services.agent_controller import run_resume_pipeline

st.set_page_config(layout="wide")
st.header("🤖 Auto Screening Decision (LangGraph Powered)")

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

threshold = st.slider(
    "✅ Selection Threshold",
    min_value=50,
    max_value=90,
    value=75
)

if st.button("⚡ Run Auto Screening"):
    if not resume_text.strip() or not jd_text.strip():
        st.warning("Please provide both resume and job description")
    else:
        with st.spinner("Executing agent workflow..."):
            output = run_resume_pipeline(
                task="screen",
                resumes=[resume_text],
                query=jd_text
            )

        decision = output["decision"]
        score = output["score"]["overall"]

        st.subheader("📊 Screening Result")

        if decision["selected"]:
            st.success("✅ Candidate Selected")
        else:
            st.error("❌ Candidate Rejected")

        st.metric("Overall Resume Score", score)

        st.subheader("🧠 Decision Explanation")
        st.write(decision["reason"])
