"""
ui/pages/01_dashboard.py — Dashboard: trigger runs + view recent MRs.
"""

import logging
import os
import queue
import sys
import threading
import time
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


for _k in ["GITLAB_TOKEN", "GITLAB_URL", "GITLAB_TARGET_PROJECT",
           "GCP_PROJECT_ID", "GCP_REGION", "GEMINI_MODEL", "GEMINI_API_KEY",
           "ARIZE_API_KEY"]:
    _v = _get(_k)
    if _v:
        os.environ.setdefault(_k, _v)

st.set_page_config(page_title="Dashboard — ShiftLeft", layout="wide")
st.title("Dashboard")

from utils.config import GITLAB_TOKEN, GITLAB_URL, GITLAB_TARGET_PROJECT
from utils.llm import backend_info

# ── Backend info banner ───────────────────────────────────────────────────────
info = backend_info()
badge = "🟢 Vertex AI" if info["backend"] == "Vertex AI" else "🟡 AI Studio (fallback)"
st.caption(f"{badge} · model `{info['model']}` · project `{info.get('project','N/A')}` · region `{info.get('region','N/A')}`")
st.divider()

# ── Constants ─────────────────────────────────────────────────────────────────
AGENTS = ["cartographer", "triage", "coder", "auditor", "hitl"]
AGENT_LABELS = {
    "cartographer": "🗺️ Cartographer",
    "triage":       "🔍 Triage",
    "coder":        "💻 Coder",
    "auditor":      "✅ Auditor",
    "hitl":         "🚀 HITL",
}


# ── Queue log handler ─────────────────────────────────────────────────────────
class _QueueHandler(logging.Handler):
    def __init__(self, q: queue.Queue):
        super().__init__()
        self.q = q

    def emit(self, record: logging.LogRecord):
        try:
            self.q.put_nowait(self.format(record))
        except queue.Full:
            pass


def _detect_agent(line: str) -> str | None:
    ll = line.lower()
    for a in AGENTS:
        if f"agents.{a}" in ll or f"] {a} —" in ll:
            return a
    return None


def _tracker_md(statuses: dict) -> str:
    return "  →  ".join(
        f"{statuses.get(a,'⏳')} **{AGENT_LABELS[a]}**" for a in AGENTS
    )


# ── Pipeline background runner ────────────────────────────────────────────────
def _run_pipeline(project: str, log_q: queue.Queue, result_holder: dict):
    root = logging.getLogger()
    handler = _QueueHandler(log_q)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)-7s] %(name)s — %(message)s", "%H:%M:%S"
    ))
    root.addHandler(handler)
    try:
        from core.graph import shiftleft_app
        from core.state import ShiftLeftState

        run_id = datetime.utcnow().strftime("%Y-%m-%d_%H%M%S")
        state: ShiftLeftState = {
            "run_id":            run_id,
            "repo_url":          f"https://gitlab.com/{project}",
            "trigger_source":    "streamlit-dashboard",
            "gitlab_project_id": project,
            "open_issues":       [],
            "branch_name":       f"shiftleft/run-{run_id}",
            "file_map":          {},
            "yaml_map":          {},
            "repo_local_path":   "",
            "issue_summary":     "",
            "target_files":      [],
            "severity":          "medium",
            "patches":           [],
            "iteration":         0,
            "test_results":      "",
            "tests_passed":      False,
            "pr_url":            "",
            "pr_number":         0,
            "diff_hunks":        [],
            "changed_files":     [],
        }
        result = shiftleft_app.invoke(state)
        result_holder["result"] = result
    except Exception as exc:
        result_holder["error"] = str(exc)
    finally:
        log_q.put("__DONE__")
        root.removeHandler(handler)


# ── Trigger section ───────────────────────────────────────────────────────────
st.subheader("Trigger a run")

project_input = st.text_input(
    "GitLab project (user/repo)",
    value=GITLAB_TARGET_PROJECT,
    placeholder="e.g. mygroup/myrepo",
)

run_btn = st.button("▶  Run ShiftLeft now", type="primary")

if run_btn and project_input.strip():
    log_q: queue.Queue = queue.Queue(maxsize=1000)
    result_holder: dict = {}

    thread = threading.Thread(
        target=_run_pipeline,
        args=(project_input.strip(), log_q, result_holder),
        daemon=True,
    )
    thread.start()

    # ── Live UI ────────────────────────────────────────────────────────────
    st.subheader("Live pipeline output")
    tracker_ph = st.empty()
    log_ph     = st.empty()
    result_ph  = st.empty()

    agent_statuses = {a: "⏳" for a in AGENTS}
    logs: list[str] = []
    current_agent: str | None = None

    while True:
        try:
            msg = log_q.get(timeout=0.12)
        except queue.Empty:
            time.sleep(0.05)
            continue

        if msg == "__DONE__":
            if current_agent:
                agent_statuses[current_agent] = "✅"
            break

        logs.append(msg)
        detected = _detect_agent(msg)
        if detected and detected != current_agent:
            if current_agent:
                agent_statuses[current_agent] = "✅"
            current_agent = detected
            agent_statuses[detected] = "🔄"

        tracker_ph.markdown(_tracker_md(agent_statuses))
        log_ph.code("\n".join(logs[-80:]))

    thread.join(timeout=10)
    tracker_ph.markdown(_tracker_md(agent_statuses))

    if "result" in result_holder:
        mr_url   = result_holder["result"].get("pr_url", "")
        severity = result_holder["result"].get("severity", "")
        summary  = result_holder["result"].get("issue_summary", "")
        tests_ok = result_holder["result"].get("tests_passed", False)

        if mr_url:
            result_ph.success(f"✅ Merge Request opened: [{mr_url}]({mr_url})")
            st.balloons()
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("Severity", severity.upper())
            col_b.metric("Tests",    "PASSED ✅" if tests_ok else "SKIPPED ⚠️")
            col_c.metric("Summary",  summary[:50] + "…" if len(summary) > 50 else summary)
        else:
            result_ph.warning("Done — no MR URL returned. Check logs above.")

    elif "error" in result_holder:
        result_ph.error(f"Pipeline failed: {result_holder['error']}")

elif run_btn:
    st.warning("Enter a GitLab project path first.")

st.divider()

# ── Recent ShiftLeft MRs ──────────────────────────────────────────────────────
st.subheader("Recent ShiftLeft Merge Requests")

col_proj, col_state = st.columns([3, 1])
project_filter = col_proj.text_input("Project", value=GITLAB_TARGET_PROJECT, key="mr_project")
mr_state_filter = col_state.selectbox("State", ["opened", "merged", "closed"])


@st.cache_data(ttl=30)
def _load_mrs(project: str, state: str):
    if not project:
        return []
    enc = project.replace("/", "%2F")
    try:
        resp = httpx.get(
            f"{GITLAB_URL}/api/v4/projects/{enc}/merge_requests",
            params={"state": state, "per_page": 20, "order_by": "updated_at"},
            headers={"PRIVATE-TOKEN": GITLAB_TOKEN},
            timeout=15,
        )
        if not resp.is_success:
            return []
        return [
            m for m in resp.json()
            if str(m.get("source_branch", "")).startswith("shiftleft/")
        ]
    except Exception:
        return []


with st.spinner("Loading MRs…"):
    mrs = _load_mrs(project_filter, mr_state_filter)

if st.button("🔄 Refresh", key="refresh_mrs"):
    st.cache_data.clear()
    st.rerun()

if not mrs:
    st.info("No ShiftLeft MRs found. Trigger a run above to create one.")
else:
    for mr in mrs:
        with st.container():
            c1, c2, c3, c4 = st.columns([5, 1, 1, 2])
            c1.markdown(f"**[!{mr['iid']} — {mr['title'][:65]}]({mr['web_url']})**")
            color = {"opened": "green", "merged": "violet", "closed": "gray"}.get(mr["state"], "gray")
            c2.markdown(f":{color}[{mr['state']}]")
            c3.caption((mr.get("created_at") or "")[:10])
            c4.link_button("Open on GitLab ↗", mr["web_url"])
            st.divider()