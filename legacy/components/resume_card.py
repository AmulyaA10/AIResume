import streamlit as st

def resume_card(name, summary, score):
    st.markdown(f"### {name}")
    st.write(summary)
    st.progress(score / 100)
