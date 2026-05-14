"""
Per-file diff viewer.
Accept incoming (keep agent patch), reject (restore original), or
open the full merge editor in vscode.dev.
"""

import streamlit as st
from tools.github_tools import (
    list_shiftleft_prs,
    get_pr_diff,
    get_file_content,
    accept_incoming,
    reject_file,
)
from utils.config import GITHUB_TARGET_REPO

st.title("🔀 Review changes")

# ── select PR ──────────────────────────────────────────────────────────────
with st.spinner("Fetching open ShiftLeft PRs…"):
    try:
        open_prs = list_shiftleft_prs(GITHUB_TARGET_REPO, state="open")
    except Exception as e:
        st.error(str(e))
        st.stop()

if not open_prs:
    st.info("No open ShiftLeft PRs to review right now.")
    st.stop()

options = {f"#{p['number']} — {p['title'][:70]}": p for p in open_prs}
choice  = st.selectbox("Select a PR to review", list(options.keys()))
pr      = options[choice]

st.markdown(
    f"**Branch:** `{pr['branch']}` → `main`  |  "
    f"[View on GitHub]({pr['url']})"
)

vsc_url = f"https://vscode.dev/github/{GITHUB_TARGET_REPO}/pull/{pr['number']}"
st.link_button("🖥  Open entire PR in VS Code", vsc_url, type="primary")

st.divider()

# ── load diffs ─────────────────────────────────────────────────────────────
with st.spinner("Fetching file diffs…"):
    try:
        diffs = get_pr_diff(GITHUB_TARGET_REPO, pr["number"])
    except Exception as e:
        st.error(f"Could not fetch diffs: {e}")
        st.stop()

if not diffs:
    st.info("No file changes found in this PR.")
    st.stop()

st.caption(f"{len(diffs)} file(s) changed in this PR.")

# ── per-file cards ─────────────────────────────────────────────────────────
for filename, diff_text in diffs.items():
    with st.expander(f"📄 `{filename}`", expanded=False):
        # count additions/removals
        additions = diff_text.count("\n+") - diff_text.count("\n+++")
        removals  = diff_text.count("\n-") - diff_text.count("\n---")
        st.caption(f"+{additions} additions   -{removals} removals")
        st.code(diff_text, language="diff", line_numbers=False)

        col1, col2, col3 = st.columns(3)

        if col1.button("✅ Accept incoming", key=f"acc_{filename}",
                       help="Keep the agent's version of this file"):
            with st.spinner("Accepting…"):
                accept_incoming(GITHUB_TARGET_REPO, pr["branch"], filename)
            st.success(f"Accepted agent changes to `{filename}`")

        if col2.button("❌ Reject (restore original)", key=f"rej_{filename}",
                       help="Revert this file to the main branch version"):
            with st.spinner("Reverting…"):
                try:
                    reject_file(GITHUB_TARGET_REPO, pr["branch"], filename)
                    st.warning(f"Reverted `{filename}` to original.")
                except Exception as e:
                    st.error(str(e))

        file_vsc = (
            f"https://vscode.dev/github/{GITHUB_TARGET_REPO}"
            f"/pull/{pr['number']}"
        )
        if col3.button("🖥  Edit in VS Code", key=f"vsc_{filename}"):
            st.markdown(
                f"[Click to open VS Code merge editor for `{filename}`]({file_vsc})"
            )