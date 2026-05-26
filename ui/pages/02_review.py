import os
import sys

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

st.set_page_config(page_title="Review MR — ShiftLeft", layout="wide", page_icon="🔍")
st.title("🔍 Review Merge Request")
st.caption("Inspect diffs from the latest ShiftLeft autonomous fix before merging.")
st.divider()


# ── Data fetchers ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=30)
def _get_mrs(project: str):
    enc = project.replace("/", "%2F")
    resp = httpx.get(
        f"{GITLAB_URL}/api/v4/projects/{enc}/merge_requests",
        params={"state": "opened", "per_page": 20, "order_by": "updated_at"},
        headers={"PRIVATE-TOKEN": GITLAB_TOKEN},
        timeout=15,
    )
    resp.raise_for_status()
    return [m for m in resp.json() if str(m.get("source_branch", "")).startswith("shiftleft/")]


@st.cache_data(ttl=30)
def _get_changes(project: str, iid: int):
    enc = project.replace("/", "%2F")
    resp = httpx.get(
        f"{GITLAB_URL}/api/v4/projects/{enc}/merge_requests/{iid}/changes",
        headers={"PRIVATE-TOKEN": GITLAB_TOKEN},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("changes", [])


# ── UI ────────────────────────────────────────────────────────────────────────

project = st.text_input("GitLab project (user/repo)", value=GITLAB_PROJECT)

if st.button("🔄 Refresh", key="refresh"):
    st.cache_data.clear()

if not project:
    st.info("Enter a GitLab project path above.")
    st.stop()

with st.spinner("Fetching open ShiftLeft MRs…"):
    try:
        mrs = _get_mrs(project)
    except Exception as exc:
        st.error(f"Could not fetch MRs: {exc}")
        st.stop()

if not mrs:
    st.info("No open ShiftLeft MRs. Trigger a run from the Dashboard.")
    st.stop()

options = {f"!{m['iid']} — {m['title'][:70]}": m for m in mrs}
choice = st.selectbox("Select Merge Request", list(options.keys()))
mr = options[choice]

# ── MR summary ────────────────────────────────────────────────────────────────
col_a, col_b, col_c = st.columns([3, 2, 2])
col_a.markdown(f"**Branch:** `{mr['source_branch']}` → `{mr['target_branch']}`")
col_b.markdown(f"**Opened:** {(mr.get('created_at') or '')[:10]}")
col_c.link_button("Open on GitLab ↗", mr["web_url"], type="primary")

# MR description in expander
with st.expander("MR Description", expanded=False):
    st.markdown(mr.get("description", "_No description._"))

st.divider()

# ── Diff viewer ───────────────────────────────────────────────────────────────
with st.spinner("Loading file diffs…"):
    try:
        changes = _get_changes(project, mr["iid"])
    except Exception as exc:
        st.error(f"Could not load changes: {exc}")
        st.stop()

source_changes = [c for c in changes if not c.get("new_path", "").startswith(".shiftleft/")]
yaml_changes   = [c for c in changes if c.get("new_path", "").startswith(".shiftleft/")]
ci_changes     = [c for c in changes if c.get("new_path", "") == ".gitlab-ci.yml"]

st.caption(
    f"**{len(source_changes)}** source file(s) changed · "
    f"**{len(yaml_changes)}** .shiftleft/ manifests · "
    f"**{len(ci_changes)}** CI config"
)

show_yaml = st.checkbox(f"Show .shiftleft/ manifests ({len(yaml_changes)} files)", value=False)
show_ci   = st.checkbox("Show .gitlab-ci.yml", value=False)

display_changes = source_changes.copy()
if show_yaml:
    display_changes += yaml_changes
if show_ci:
    display_changes += ci_changes

# ── Per-file diff panels ──────────────────────────────────────────────────────
for change in display_changes:
    path     = change.get("new_path") or change.get("old_path", "?")
    diff_raw = change.get("diff", "")
    added   = sum(1 for l in diff_raw.splitlines() if l.startswith("+") and not l.startswith("+++"))
    removed = sum(1 for l in diff_raw.splitlines() if l.startswith("-") and not l.startswith("---"))

    is_source = not path.startswith(".shiftleft/") and path != ".gitlab-ci.yml"
    label = f"`{path}`  (+{added} / -{removed})"

    with st.expander(label, expanded=is_source):
        if diff_raw.strip():
            st.code(diff_raw, language="diff")
        else:
            st.caption("(empty diff — file may be new with no previous version)")

        gl_diff_url = f"{mr['web_url']}/diffs#{path.replace('/', '_')}"
        st.link_button("View on GitLab ↗", mr["web_url"] + "/diffs")