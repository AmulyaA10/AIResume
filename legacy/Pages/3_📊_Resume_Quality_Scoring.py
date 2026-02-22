import streamlit as st
from services.agent_controller import run_resume_pipeline




st.header("📊 Resume Quality Scoring (LangGraph)")

resume_text = st.text_area(
    "Paste Resume Text",
    height=300,
    placeholder="Paste candidate resume here..."
)

if st.button("📈 Score Resume"):
    if not resume_text.strip():
        st.warning("Please paste resume text")
    else:
        with st.spinner("Running quality scoring agent..."):
            output = run_resume_pipeline(
                task="score",
                resumes=[resume_text]
            )

        score = output["score"]["overall"]

        st.metric("Overall Resume Score", score)

        st.subheader("Score Breakdown")
        st.json(output["score"])
