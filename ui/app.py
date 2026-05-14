import streamlit as st

st.set_page_config(
    page_title="ShiftLeft",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.sidebar.title("🔍 ShiftLeft")
st.sidebar.caption("Autonomous open-source checker")
st.sidebar.divider()
st.sidebar.page_link("ui/app.py",                  label="🏠  Home")
st.sidebar.page_link("ui/pages/01_dashboard.py",   label="📊  Dashboard")
st.sidebar.page_link("ui/pages/02_review.py",      label="🔀  Review changes")
st.sidebar.page_link("ui/pages/03_scheduler.py",   label="⏱   Scheduler")

st.title("ShiftLeft")
st.markdown("""
**Autonomous open-source code intelligence.**

ShiftLeft monitors your GitHub repository, triages code quality issues with Gemini AI,
generates verified patches, and opens Pull Requests — automatically.

| Page | What it does |
|---|---|
| 📊 Dashboard | View run history, open PRs, and trigger a new run |
| 🔀 Review changes | Accept, reject, or open individual file diffs in VS Code |
| ⏱ Scheduler | Configure automated nightly runs via Cloud Scheduler |
""")