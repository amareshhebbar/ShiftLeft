"""
GitHub API operations used by ShiftLeft.
All functions are stateless and re-authenticate on every call
so they work correctly in Cloud Run's ephemeral containers.
"""

import re
import httpx
from github import Github, GithubException
from typing import Dict, List, Optional

from utils.config import GITHUB_TOKEN, DEFAULT_BASE_BRANCH
from utils.logger import get_logger

log = get_logger(__name__)


def _client() -> Github:
    return Github(GITHUB_TOKEN)


def _repo(repo_name: str):
    return _client().get_repo(repo_name)


# ── Branch operations ──────────────────────────────────────────────────────

def create_branch(repo_name: str, branch: str, base: str = None) -> bool:
    """Create a new branch from base. Returns True if created or already exists."""
    base = base or DEFAULT_BASE_BRANCH
    r = _repo(repo_name)
    sha = r.get_branch(base).commit.sha
    try:
        r.create_git_ref(ref=f"refs/heads/{branch}", sha=sha)
        log.info(f"[github] created branch: {branch}")
        return True
    except GithubException as e:
        if e.status == 422:   # already exists — that is fine
            log.info(f"[github] branch already exists: {branch}")
            return True
        log.error(f"[github] create_branch failed: {e}")
        raise


# ── Commit operations ──────────────────────────────────────────────────────

def commit_files(
    repo_name: str,
    branch: str,
    files: Dict[str, str],        # {repo-relative-path: content-string}
    message: str = "chore(shiftleft): automated patch",
) -> str:
    """
    Commit multiple files to a branch in a single API round-trip using
    the Git Data API (blobs → tree → commit → ref update).
    Returns the new commit SHA.
    """
    r = _repo(repo_name)
    ref       = r.get_git_ref(f"heads/{branch}")
    base_sha  = ref.object.sha
    base_tree = r.get_git_commit(base_sha).tree

    blobs = []
    for path, content in files.items():
        blob = r.create_git_blob(content, "utf-8")
        blobs.append({
            "path": path,
            "mode": "100644",
            "type": "blob",
            "sha":  blob.sha,
        })

    new_tree   = r.create_git_tree(blobs, base_tree)
    new_commit = r.create_git_commit(
        message, new_tree, [r.get_git_commit(base_sha)]
    )
    ref.edit(new_commit.sha)
    log.info(f"[github] committed {len(files)} file(s) to {branch} "
             f"({new_commit.sha[:7]})")
    return new_commit.sha


# ── Pull request operations ────────────────────────────────────────────────

def open_pr(
    repo_name: str,
    branch: str,
    title: str,
    body: str,
    base: str = None,
) -> Dict:
    """
    Open a pull request. Returns {"pr_number": int, "pr_url": str}.
    Raises GithubException on failure (caller handles).
    """
    base = base or DEFAULT_BASE_BRANCH
    r = _repo(repo_name)
    pr = r.create_pull(title=title, body=body, head=branch, base=base)
    log.info(f"[github] opened PR #{pr.number}: {pr.html_url}")
    return {"pr_number": pr.number, "pr_url": pr.html_url}


def get_pr_diff(repo_name: str, pr_number: int) -> Dict[str, str]:
    """
    Fetch the raw unified diff for a PR and split it into per-file chunks.
    Returns {filename: diff_string}.
    """
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept":        "application/vnd.github.v3.diff",
    }
    url  = f"https://api.github.com/repos/{repo_name}/pulls/{pr_number}"
    resp = httpx.get(url, headers=headers, timeout=30)
    resp.raise_for_status()

    raw    = resp.text
    chunks = re.split(r"(?=^diff --git )", raw, flags=re.MULTILINE)
    diffs: Dict[str, str] = {}
    for chunk in chunks:
        if not chunk.strip():
            continue
        m = re.match(r"diff --git a/(.+?) b/", chunk)
        if m:
            diffs[m.group(1)] = chunk
    return diffs


def get_file_content(repo_name: str, path: str, ref: str) -> str:
    """Fetch a file's content from a specific branch/ref."""
    r = _repo(repo_name)
    return r.get_contents(path, ref=ref).decoded_content.decode("utf-8", errors="replace")


def list_shiftleft_prs(repo_name: str, state: str = "open") -> List[Dict]:
    """Return all PRs whose head branch starts with 'shiftleft/'."""
    r = _repo(repo_name)
    return [
        {
            "number":  pr.number,
            "title":   pr.title,
            "state":   pr.state,
            "url":     pr.html_url,
            "branch":  pr.head.ref,
            "created": pr.created_at.isoformat(),
        }
        for pr in r.get_pulls(state=state, sort="created", direction="desc")
        if pr.head.ref.startswith("shiftleft/")
    ]


# ── Review helpers (used by Streamlit review page) ────────────────────────

def accept_incoming(repo_name: str, branch: str, filename: str) -> str:
    """Accept the agent's version — no-op since the branch already has it."""
    # The agent's content IS already on the branch.
    # This function exists as a clear API contract; it just logs acceptance.
    log.info(f"[github] accepted incoming: {filename} on {branch}")
    return "accepted"


def reject_file(repo_name: str, branch: str, filename: str, base: str = None) -> str:
    """
    Reject the agent's change: restore the file content from base branch,
    effectively reverting just this file on the PR branch.
    """
    base = base or DEFAULT_BASE_BRANCH
    original = get_file_content(repo_name, filename, base)
    return commit_files(
        repo_name, branch,
        {filename: original},
        message=f"review: reject agent changes to {filename}",
    )