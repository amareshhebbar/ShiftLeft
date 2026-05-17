import os, sys, threading
from datetime import datetime
import httpx
import streamlit as st

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

def _get(key, default=""):
    try:
        return st.secrets[key]
    except Exception:
        return os.environ.get(key, default)

GITLAB_TOKEN   = _get("GITLAB_TOKEN")
GITLAB_URL     = _get("GITLAB_URL", "https://gitlab.com")
GITLAB_PROJECT = _get("GITLAB_TARGET_PROJECT", "")

os.environ["GITLAB_TOKEN"]          = GITLAB_TOKEN
os.environ["GITLAB_URL"]            = GITLAB_URL
os.environ["GITLAB_TARGET_PROJECT"] = GITLAB_PROJECT
os.environ["GEMINI_API_KEY"]        = _get("GEMINI_API_KEY")
os.environ["GEMINI_MODEL"]          = _get("GEMINI_MODEL", "gemini-2.5-flash")

st.set_page_config(page_title="Dashboard — ShiftLeft", layout="wide")
st.title("Dashboard")

# ── Trigger ────────────────────────────────────────────────────────────────
st.subheader("Trigger a run")
project_input = st.text_input("GitLab project (user/repo)", value=GITLAB_PROJECT)

if st.button("▶  Run ShiftLeft now", type="primary"):
    st.info("Pipeline running — takes ~60 seconds…")

    def _run():
        from core.graph import shiftleft_app
        from core.state import ShiftLeftState
        run_id = datetime.utcnow().strftime("%Y-%m-%d_%H%M%S")
        state: ShiftLeftState = {
            "run_id": run_id, "repo_url": f"https://gitlab.com/{project_input}",
            "trigger_source": "streamlit", "gitlab_project_id": project_input,
            "open_issues": [], "branch_name": f"shiftleft/run-{run_id}",
            "file_map": {}, "yaml_map": {}, "repo_local_path": "",
            "issue_summary": "", "target_files": [], "severity": "medium",
            "patches": [], "iteration": 0, "test_results": "",
            "tests_passed": False, "pr_url": "", "pr_number": 0,
            "diff_hunks": [], "changed_files": [],
        }
        try:
            result = shiftleft_app.invoke(state)
            st.session_state["last_result"] = result
        except Exception as e:
            st.session_state["last_error"] = str(e)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    with st.spinner("Running…"): t.join(timeout=180)

    if "last_result" in st.session_state:
        mr_url = st.session_state["last_result"].get("pr_url", "")
        if mr_url:
            st.success(f"MR created: [{mr_url}]({mr_url})")
            st.balloons()
        else:
            st.warning("Done — no MR URL returned. Check logs.")
    elif "last_error" in st.session_state:
        st.error(st.session_state["last_error"])

st.divider()

# ── Recent MRs ─────────────────────────────────────────────────────────────
st.subheader("Recent ShiftLeft Merge Requests")
mr_state = st.selectbox("Filter", ["opened", "merged", "closed"])

def _load_mrs(project, state):
    enc = project.replace("/", "%2F")
    resp = httpx.get(
        f"{GITLAB_URL}/api/v4/projects/{enc}/merge_requests",
        params={"state": state, "per_page": 20},
        headers={"PRIVATE-TOKEN": GITLAB_TOKEN}, timeout=15,
    )
    if not resp.is_success: return []
    return [m for m in resp.json()
            if str(m.get("source_branch","")).startswith("shiftleft/")]

with st.spinner("Loading…"):
    try: mrs = _load_mrs(project_input, mr_state)
    except Exception as e: st.error(str(e)); mrs = []

if not mrs:
    st.info("No ShiftLeft MRs yet. Trigger a run above.")
else:
    for mr in mrs:
        c1,c2,c3,c4 = st.columns([4,1,1,2])
        c1.markdown(f"**[!{mr['iid']} {mr['title'][:60]}]({mr['web_url']})**")
        color = "green" if mr["state"]=="opened" else "gray"
        c2.markdown(f":{color}[{mr['state']}]")
        c3.caption((mr.get("created_at",""))[:10])
        c4.link_button("Open ↗", mr["web_url"])
