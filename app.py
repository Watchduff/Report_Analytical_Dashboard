"""
Report Analytics Dashboard
BYU-Hawaii Office of Information Technology

Entry point / page router. Run with: streamlit run app.py
"""

import streamlit as st

st.set_page_config(
    page_title="Report Analytics Dashboard",
    page_icon="📊",
    layout="wide",
)

page = st.navigation([
    st.Page("app_pages/dashboard.py", title="Dashboard", icon=":material/dashboard:", default=True),
    st.Page("app_pages/presentation.py", title="Presentation", icon=":material/slideshow:"),
])

page.run()
