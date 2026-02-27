import streamlit as st

st.header("📥 Reports & Export")

format = st.selectbox("Export Format", ["PDF", "CSV"])

if st.button("⬇️ Download"):
    st.success("Report ready for download")
