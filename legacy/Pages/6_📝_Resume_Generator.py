import streamlit as st
from services.agent_controller import run_resume_pipeline
from services.export_service import generate_docx
import json

st.header("📝 AI Resume Generator")

profile = st.text_area(
    "Describe your skills, experience, and education",
    placeholder="I am a software engineer with 5 years of experience in Python and AWS. I studied at IIT Bombay...",
    height=200
)

col1, col2 = st.columns([1, 4])

if col1.button("✨ Generate Resume"):
    if not profile.strip():
        st.warning("Please describe your profile first.")
    else:
        with st.spinner("Writing your professional resume..."):
            output = run_resume_pipeline(
                task="generate",
                query=profile
            )
            
            resume_json = output["resume_json"]
            st.session_state["generated_resume"] = resume_json

if "generated_resume" in st.session_state:
    resume = st.session_state["generated_resume"]
    
    st.subheader("Preview")
    
    # Display in a nice format
    contact = resume.get("contact", {})
    st.markdown(f"### {contact.get('name', 'Your Name')}")
    st.markdown(f"{contact.get('email', '')} | {contact.get('phone', '')} | {contact.get('location', '')}")
    
    st.markdown("#### Professional Summary")
    st.write(resume.get("summary", ""))
    
    st.markdown("#### Key Skills")
    st.write(", ".join(resume.get("skills", [])))
    
    st.markdown("#### Work Experience")
    for exp in resume.get("experience", []):
        st.markdown(f"**{exp.get('title')}** at *{exp.get('company')}* ({exp.get('period')})")
        for bullet in exp.get("bullets", []):
            st.markdown(f"- {bullet}")
            
    st.markdown("#### Education")
    for edu in resume.get("education", []):
        st.markdown(f"**{edu.get('degree')}**, {edu.get('school')} ({edu.get('year')})")

    # Word Export
    docx_file = generate_docx(resume)
    
    st.download_button(
        label="📥 Download as Word",
        data=docx_file,
        file_name=f"{contact.get('name', 'resume').replace(' ', '_')}_resume.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
