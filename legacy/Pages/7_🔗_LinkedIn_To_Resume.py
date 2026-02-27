# Pages/LinkedIn_To_Resume.py
import streamlit as st
from services.agent_controller import generate_resume_from_linkedin

st.set_page_config(layout="wide")
st.header("🔗 LinkedIn → Resume (LangGraph AI)")

linkedin_url = st.text_input(
    "LinkedIn Profile URL",
    placeholder="https://www.linkedin.com/in/username"
)

if st.button("🔄 Generate Resume"):
    if not linkedin_url.strip():
        st.warning("Please enter a LinkedIn URL")
    else:
        with st.spinner("Generating resume using AI agents..."):
            output = generate_resume_from_linkedin(linkedin_url)

        st.subheader("📄 Generated Resume")
        st.text_area(
            "Resume",
            output["resume"],
            height=500
        )
