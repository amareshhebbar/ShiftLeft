"""
ui/app.py — ShiftLeft Streamlit entry point.

Features:
  - Live pipeline execution with real-time log streaming
  - 5-agent visual tracker (Cartographer → Triage → Coder → Auditor → HITL)
  - Vertex AI / AI Studio backend badge
  - Arize Phoenix tracing status
"""

import logging
import os
import queue
import sys
import threading
import time
from datetime import datetime

import streamlit as st

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="ShiftLeft — Autonomous Bug Fixer",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Path setup ────────────────────────────────────────────────────────────────
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# ── Env injection from Streamlit secrets ─────────────────────────────────────
def _sync_secrets():
    keys = [
        "GITLAB_TOKEN", "GITLAB_URL", "GITLAB_TARGET_PROJECT",
        "GCP_PROJECT_ID", "GCP_REGION", "GEMINI_MODEL", "GEMINI_API_KEY",
        "ARIZE_API_KEY", "PHOENIX_ENDPOINT", "WEBHOOK_SECRET",
    ]
    for k in keys:
        try:
            v = st.secrets[k]
            if v:
                os.environ.setdefault(k, v)
        except Exception:
            pass

_sync_secrets()

from utils.llm import backend_info
from utils.tracing import init_tracing

# Init Arize tracing once
init_tracing()

AGENTS = ["cartographer", "triage", "coder", "auditor", "hitl"]
AGENT_LABELS = {
    "cartographer": "🗺️ Cartographer",
    "triage":       "🔍 Triage",
    "coder":        "💻 Coder",
    "auditor":      "✅ Auditor",
    "hitl":         "🚀 HITL",
}

# ── Custom log handler that pushes to a queue ─────────────────────────────────
class _QueueHandler(logging.Handler):
    def __init__(self, q: queue.Queue):
        super().__init__()
        self.q = q

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            self.q.put_nowait(msg)
        except queue.Full:
            pass


def _detect_agent(log_line: str) -> str | None:
    ll = log_line.lower()
    for a in AGENTS:
        if f"agents.{a}" in ll or f"] {a} —" in ll:
            return a
    return None


def _render_agent_tracker(statuses: dict) -> str:
    parts = []
    for a in AGENTS:
        icon = statuses.get(a, "⏳")
        label = AGENT_LABELS[a]
        parts.append(f"{icon} {label}")
    return "  →  ".join(parts)


# ── Pipeline runner in background thread ──────────────────────────────────────
def _run_pipeline(project: str, log_q: queue.Queue, result_holder: dict):
    root_logger = logging.getLogger()
    handler = _QueueHandler(log_q)
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s — %(message)s", "%H:%M:%S")
    )
    root_logger.addHandler(handler)

    try:
        from core.graph import shiftleft_app
        from core.state import ShiftLeftState

        run_id = datetime.utcnow().strftime("%Y-%m-%d_%H%M%S")
        initial: ShiftLeftState = {
            "run_id":             run_id,
            "repo_url":           f"https://gitlab.com/{project}",
            "trigger_source":     "streamlit",
            "gitlab_project_id":  project,
            "open_issues":        [],
            "branch_name":        f"shiftleft/run-{run_id}",
            "file_map":           {},
            "yaml_map":           {},
            "repo_local_path":    "",
            "issue_summary":      "",
            "target_files":       [],
            "severity":           "medium",
            "patches":            [],
            "iteration":          0,
            "test_results":       "",
            "tests_passed":       False,
            "pr_url":             "",
            "pr_number":          0,
            "diff_hunks":         [],
            "changed_files":      [],
        }
        result = shiftleft_app.invoke(initial)
        result_holder["result"] = result
    except Exception as exc:
        result_holder["error"] = str(exc)
    finally:
        log_q.put("__DONE__")
        root_logger.removeHandler(handler)


# ── Main app layout ───────────────────────────────────────────────────────────
st.markdown("# 🔧 ShiftLeft")
st.markdown("**Autonomous Bug-Fixing Agent for GitLab** — powered by Gemini on Vertex AI")

# Backend badge
info = backend_info()
badge_color = "🟢" if info["backend"] == "Vertex AI" else "🟡"
st.caption(
    f"{badge_color} LLM: **{info['backend']}** · model `{info['model']}` · "
    f"project `{info.get('project','N/A')}` · region `{info.get('region','N/A')}`"
)

st.divider()

# ── Sidebar nav ───────────────────────────────────────────────────────────────
st.sidebar.title("Navigation")
st.sidebar.page_link("app.py",               label="🏠 Home")
st.sidebar.page_link("pages/01_dashboard.py", label="📊 Dashboard")
st.sidebar.page_link("pages/02_review.py",    label="🔍 Review MR")
st.sidebar.page_link("pages/03_scheduler.py", label="⏱ Scheduler")

# ── Quick run panel ───────────────────────────────────────────────────────────
from utils.config import GITLAB_TARGET_PROJECT

project_input = st.text_input(
    "GitLab project (user/repo)",
    value=GITLAB_TARGET_PROJECT,
    placeholder="e.g. myuser/myrepo",
)

col_run, col_info = st.columns([2, 3])
run_btn = col_run.button("▶  Run ShiftLeft now", type="primary", use_container_width=True)
col_info.info("The pipeline takes ~60 seconds. Logs stream live below.")

# ── Live streaming run ────────────────────────────────────────────────────────
if run_btn and project_input.strip():
    log_q: queue.Queue = queue.Queue(maxsize=1000)
    result_holder: dict = {}

    thread = threading.Thread(
        target=_run_pipeline,
        args=(project_input.strip(), log_q, result_holder),
        daemon=True,
    )
    thread.start()

    st.subheader("Pipeline Progress")
    tracker_ph = st.empty()
    log_ph     = st.empty()
    done_ph    = st.empty()

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
            # Mark all completed agents as done
            for a in AGENTS:
                if agent_statuses[a] == "🔄":
                    agent_statuses[a] = "✅"
            break

        logs.append(msg)

        # Detect agent transitions
        detected = _detect_agent(msg)
        if detected and detected != current_agent:
            if current_agent:
                agent_statuses[current_agent] = "✅"
            current_agent = detected
            agent_statuses[detected] = "🔄"

        tracker_ph.markdown(
            f"**{_render_agent_tracker(agent_statuses)}**"
        )
        log_ph.code("\n".join(logs[-70:]), language="")

    thread.join(timeout=10)

    # Final tracker update
    tracker_ph.markdown(f"**{_render_agent_tracker(agent_statuses)}**")

    if "result" in result_holder:
        mr_url = result_holder["result"].get("pr_url", "")
        severity = result_holder["result"].get("severity", "")
        summary  = result_holder["result"].get("issue_summary", "")
        if mr_url:
            done_ph.success(f"✅ Done! Merge Request created: [{mr_url}]({mr_url})")
            st.balloons()
            st.markdown(f"**Severity:** `{severity}` · **Summary:** {summary}")
        else:
            done_ph.warning("Pipeline completed — no MR URL returned. Check logs above.")
    elif "error" in result_holder:
        done_ph.error(f"Pipeline failed: {result_holder['error']}")
elif run_btn:
    st.warning("Enter a GitLab project path first.")

# ── Info cards ────────────────────────────────────────────────────────────────
st.divider()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Agents",        "5",              help="Cartographer → Triage → Coder → Auditor → HITL")
c2.metric("LLM",           "Gemini",         help="Via Vertex AI (Google Cloud)")
c3.metric("Integration",   "GitLab MCP",     help="Branch creation via MCP protocol")
c4.metric("Languages",     "Python + JS/TS", help="Multi-language syntax validation")