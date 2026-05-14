"""Run history, open PR list, and manual trigger."""

import httpx
import streamlit as st

from tools.github_tools import list_shiftleft_prs
from utils.config import CLOUD_RUN_URL, GITHUB_TARGET_REPO

st.title("📊 Dashboard")

# ── Manual trigger ─────────────────────────────────────────────────────────
st.subheader("Trigger a run")
repo_input = st.text_input(
    "GitHub repository (owner/name)",
    value=GITHUB_TARGET_REPO,
    help="e.g. torvalds/linux",
)

if st.button("▶  Run ShiftLeft now", type="primary"):
    with st.spinner("Queuing run on Cloud Run…"):
        try:
            resp = httpx.post(
                f"{CLOUD_RUN_URL}/webhook/scheduler",
                json={"source": "manual", "repo_url":
                      f"https://github.com/{repo_input}.git"},
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                st.success(f"Queued! Run ID: `{data.get('run_id', 'unknown')}`")
                st.info("Check GitHub for the new PR in a few minutes.")
            else:
                st.error(f"Webhook returned HTTP {resp.status_code}: {resp.text}")
        except httpx.ConnectError:
            st.error("Could not reach Cloud Run. Is CLOUD_RUN_URL set correctly?")
        except Exception as e:
            st.error(str(e))

st.divider()

# ── PR history ─────────────────────────────────────────────────────────────
st.subheader("Recent ShiftLeft pull requests")

col_filter1, col_filter2 = st.columns(2)
pr_state = col_filter1.selectbox("Filter by state", ["open", "closed", "all"])
max_prs  = col_filter2.number_input("Show last N PRs", min_value=1,
                                     max_value=50, value=10)

with st.spinner("Loading pull requests…"):
    try:
        prs = list_shiftleft_prs(GITHUB_TARGET_REPO, state=pr_state)[:max_prs]
    except Exception as e:
        st.error(f"GitHub API error: {e}")
        prs = []

if not prs:
    st.info("No ShiftLeft pull requests found.")
else:
    for pr in prs:
        c1, c2, c3, c4 = st.columns([3, 1, 1, 2])
        c1.markdown(f"**[#{pr['number']} {pr['title'][:60]}]({pr['url']})**")
        badge_color = "green" if pr["state"] == "open" else "gray"
        c2.markdown(f":{badge_color}[{pr['state']}]")
        c3.caption(pr["created"][:10])
        vsc = f"https://vscode.dev/github/{GITHUB_TARGET_REPO}/pull/{pr['number']}"
        c4.link_button("Open in VS Code ↗", vsc)