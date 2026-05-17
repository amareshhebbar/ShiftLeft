import streamlit as st

st.set_page_config(
    page_title="ShiftLeft", layout="wide",
    initial_sidebar_state="expanded",
)

st.title("ShiftLeft")
st.markdown("### Autonomous Bug-Fixing Agent for GitLab")
st.markdown("""
ShiftLeft reads any GitLab repository, finds the highest-impact bug using **Gemini 3.1 Pro**,
writes a fix, validates it, and opens a **Merge Request** — without a human writing a single line of code.
""")

st.divider()
col1, col2, col3 = st.columns(3)
col1.metric("Agents", "5", help="Cartographer → Triage → Coder → Auditor → HITL")
col2.metric("LLM", "Gemini 3.1 Pro", help="1M token context window")
col3.metric("Integration", "GitLab MCP", help="Branch creation via MCP protocol")
st.divider()

st.markdown("""
| Page | What it does |
|---|---|
|**Dashboard** | Trigger a run, view recent GitLab MRs |
|**Review MR** | See the diff, open MR on GitLab |
|**Scheduler** | Configure automated nightly runs |
""")
st.info("Go to **Dashboard** in the sidebar to trigger your first run.")
