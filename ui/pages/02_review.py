import os, sys
import httpx
import streamlit as st

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

def _get(key, default=""):
    try: return st.secrets[key]
    except Exception: return os.environ.get(key, default)

GITLAB_TOKEN   = _get("GITLAB_TOKEN")
GITLAB_URL     = _get("GITLAB_URL", "https://gitlab.com")
GITLAB_PROJECT = _get("GITLAB_TARGET_PROJECT", "")

st.set_page_config(page_title="Review MR — ShiftLeft", layout="wide")
st.title("Review Merge Request")

project = st.text_input("GitLab project", value=GITLAB_PROJECT)

def _get_mrs(project):
    enc = project.replace("/", "%2F")
    resp = httpx.get(
        f"{GITLAB_URL}/api/v4/projects/{enc}/merge_requests",
        params={"state": "opened", "per_page": 20},
        headers={"PRIVATE-TOKEN": GITLAB_TOKEN}, timeout=15,
    )
    resp.raise_for_status()
    return [m for m in resp.json()
            if str(m.get("source_branch","")).startswith("shiftleft/")]

def _get_changes(project, iid):
    enc = project.replace("/", "%2F")
    resp = httpx.get(
        f"{GITLAB_URL}/api/v4/projects/{enc}/merge_requests/{iid}/changes",
        headers={"PRIVATE-TOKEN": GITLAB_TOKEN}, timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("changes", [])

with st.spinner("Fetching open ShiftLeft MRs…"):
    try: mrs = _get_mrs(project)
    except Exception as e: st.error(str(e)); st.stop()

if not mrs:
    st.info("No open ShiftLeft MRs. Trigger a run from Dashboard.")
    st.stop()

options = {f"!{m['iid']} — {m['title'][:70]}": m for m in mrs}
choice  = st.selectbox("Select MR", list(options.keys()))
mr      = options[choice]

st.markdown(f"**Branch:** `{mr['source_branch']}` → `{mr['target_branch']}`")
st.link_button("Open on GitLab", mr["web_url"], type="primary")
st.divider()

with st.spinner("Loading diffs…"):
    try: changes = _get_changes(project, mr["iid"])
    except Exception as e: st.error(str(e)); st.stop()

source = [c for c in changes if not c.get("new_path","").startswith(".shiftleft/")]
yamls  = [c for c in changes if c.get("new_path","").startswith(".shiftleft/")]
show_yaml = st.checkbox(f"Show .shiftleft/ manifests ({len(yamls)} files)", value=False)
all_changes = source + (yamls if show_yaml else [])

st.caption(f"{len(source)} source file(s) changed · {len(yamls)} manifest(s)")

for change in all_changes:
    path = change.get("new_path") or change.get("old_path","?")
    diff = change.get("diff","")
    added   = diff.count("\n+") - diff.count("\n+++")
    removed = diff.count("\n-") - diff.count("\n---")
    with st.expander(f"`{path}`  (+{added} / -{removed})",
                     expanded=not path.startswith(".shiftleft/")):
        if diff: st.code(diff, language="diff")
        else: st.caption("(empty diff)")
        st.link_button("View on GitLab ↗", mr["web_url"] + "/diffs")
