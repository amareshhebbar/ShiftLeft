import streamlit as st
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.graph import shiftleft_app
from core.state import ShiftLeftState

st.set_page_config(page_title="ShiftLeft", page_icon="⚙️", layout="wide")

st.title("⚙️ ShiftLeft: Autonomous Co-Maintainer")
st.markdown("Enter a GitHub issue below. ShiftLeft will map the repo, write a fix, and verify it in an isolated sandbox.")

issue_text = st.text_area("GitHub Issue Description", "Bug: Database connection drops under load.")

if st.button("Trigger Autonomous Fix", type="primary"):
    initial_state: ShiftLeftState = {
        "issue_text": issue_text,
        "repo_map": {},
        "current_code": "",
        "test_results": {},
        "error_logs": "",
        "agent_messages": [],
        "tests_passed": False,
        "requires_human": False
    }

    status_container = st.container()
    logs_placeholder = st.empty()
    
    with st.spinner("Agents are working..."):
        full_logs = []
        for output in shiftleft_app.stream(initial_state):
            for node_name, node_state in output.items():
                messages = node_state.get("agent_messages", [])
                if messages:
                    latest_msg = messages[-1]
                    full_logs.append(f"**[{node_name.upper()}]** {latest_msg}")
                    logs_placeholder.markdown("\n\n".join(full_logs))
        final_state = output.get("hitl", {})
        
        if final_state:
            st.success("Workflow Complete! Review the PR below.")
            st.markdown(final_state.get("error_logs", ""))
            
            st.button("Approve & Merge Pull Request", type="primary", use_container_width=True)