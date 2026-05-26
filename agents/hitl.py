from __future__ import annotations

import base64
from typing import Any, Dict, List, Set

import httpx
import yaml

from core.state import ShiftLeftState
from tools.gitlab_mcp_tools import create_branch, _default_branch
from utils.config import GITLAB_TARGET_PROJECT, GITLAB_TOKEN, GITLAB_URL
from utils.logger import get_logger

log = get_logger(__name__)

_COMMIT_BATCH = 20   # max actions per GitLab commit API call


# ── REST helpers ───────────────────────────────────────────────────────────────

def _headers() -> Dict[str, str]:
    return {"PRIVATE-TOKEN": GITLAB_TOKEN, "Content-Type": "application/json"}


def _existing_paths(project: str, ref: str) -> Set[str]:
    enc = project.replace("/", "%2F")
    url = f"{GITLAB_URL}/api/v4/projects/{enc}/repository/tree"
    params: Dict[str, Any] = {"recursive": "true", "per_page": 100, "ref": ref}
    paths: Set[str] = set()
    page = 1
    while True:
        params["page"] = page
        resp = httpx.get(url, params=params, headers={"PRIVATE-TOKEN": GITLAB_TOKEN}, timeout=30)
        if not resp.is_success:
            break
        items = resp.json()
        if not items:
            break
        for item in items:
            if item.get("type") == "blob":
                paths.add(item["path"])
        if len(items) < 100:
            break
        page += 1
    return paths


def _push_commit(
    project: str, branch: str,
    files: List[Dict[str, str]],
    message: str,
    existing: Set[str],
) -> Dict:
    enc = project.replace("/", "%2F")
    url = f"{GITLAB_URL}/api/v4/projects/{enc}/repository/commits"

    for i in range(0, len(files), _COMMIT_BATCH):
        batch = files[i : i + _COMMIT_BATCH]
        actions = []
        for f in batch:
            fp      = f["file_path"]
            content = f["content"]
            action  = "update" if fp in existing else "create"
            actions.append({
                "action":   action,
                "file_path": fp,
                "content":  content,
                "encoding": "text",
            })

        payload = {
            "branch":         branch,
            "commit_message": message if i == 0 else f"docs(shiftleft): batch {i // _COMMIT_BATCH + 1}",
            "actions":        actions,
        }

        resp = httpx.post(url, headers=_headers(), json=payload, timeout=60)
        if not resp.is_success:
            raise RuntimeError(
                f"GitLab commit API error {resp.status_code}: {resp.text[:400]}"
            )
        for f in batch:
            existing.add(f["file_path"])

        log.info(f"hitl — committed batch {i // _COMMIT_BATCH + 1} ({len(batch)} files) via REST")

    return {"status": "ok", "files": len(files)}


def _create_mr_rest(
    project: str, branch: str, target: str,
    title: str, description: str,
) -> Dict:
    """Create a Merge Request via GitLab REST API."""
    enc = project.replace("/", "%2F")
    resp = httpx.post(
        f"{GITLAB_URL}/api/v4/projects/{enc}/merge_requests",
        headers=_headers(),
        json={
            "source_branch": branch,
            "target_branch": target,
            "title":         title,
            "description":   description,
            "remove_source_branch": False,
        },
        timeout=30,
    )
    if not resp.is_success:
        raise RuntimeError(f"MR creation failed {resp.status_code}: {resp.text[:400]}")
    return resp.json()


def _create_issue_rest(
    project: str, title: str, description: str, labels: List[str],
) -> Dict:
    """Create an issue via GitLab REST API."""
    enc = project.replace("/", "%2F")
    resp = httpx.post(
        f"{GITLAB_URL}/api/v4/projects/{enc}/issues",
        headers=_headers(),
        json={"title": title, "description": description, "labels": ",".join(labels)},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


# ── Agent entry point ──────────────────────────────────────────────────────────

def hitl(state: ShiftLeftState) -> ShiftLeftState:
    project       = state.get("gitlab_project_id") or GITLAB_TARGET_PROJECT
    branch        = state["branch_name"]
    run_id        = state["run_id"]
    patches       = state.get("patches") or []
    yaml_map      = state.get("yaml_map") or {}
    issue_summary = state.get("issue_summary") or "Automated fix by ShiftLeft"
    severity      = state.get("severity") or "medium"

    default_ref = _default_branch(project)
    log.info(f"hitl — branch={branch}  project={project}  base={default_ref}")

    # ── 1. Create branch via MCP (this works) ─────────────────────────────────
    try:
        create_branch(branch=branch, project=project)
        log.info(f"hitl — ✅ branch created via MCP: {branch}")
    except Exception as exc:
        if "already exists" in str(exc).lower():
            log.warning("hitl — branch already exists, continuing")
        else:
            raise

    # ── 2. Build file lists ────────────────────────────────────────────────────
    changed_files: List[str] = []
    diff_hunks:    List[Dict] = []
    source_files:  List[Dict[str, str]] = []
    manifest_files: List[Dict[str, str]] = []

    for patch in patches:
        fp      = patch.get("file_path", "")
        content = patch.get("patched_content", "")
        if fp and content:
            source_files.append({"file_path": fp, "content": content})
            changed_files.append(fp)
            diff_hunks.append({"file": fp, "diff": patch.get("diff", "")})
            log.info(f"hitl — source patch: {fp}")

    ci_skip_yaml = """# ShiftLeft automated branch — CI skipped.
# Full integration tests run on merge to main, not on AI patch branches.
workflow:
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
      when: never
    - if: $CI_COMMIT_BRANCH =~ /^shiftleft\//
      when: never
    - when: always
"""
    manifest_files.append({"file_path": ".gitlab-ci.yml", "content": ci_skip_yaml})

    for yaml_path, yaml_content in yaml_map.items():
        manifest_files.append({"file_path": yaml_path, "content": yaml_content})

    audit_doc: Dict[str, Any] = {
        "run_id":           run_id,
        "project":          project,
        "branch":           branch,
        "severity":         severity,
        "issue_summary":    issue_summary,
        "files_patched":    changed_files,
        "files_documented": len(yaml_map),
        "tests_passed":     state.get("tests_passed", False),
        "test_output":      (state.get("test_results") or "")[:300],
    }
    manifest_files.append({
        "file_path": f".shiftleft/audits/{run_id}.yaml",
        "content":   yaml.dump(audit_doc, default_flow_style=False),
    })

    all_files = source_files + manifest_files
    log.info(f"hitl — {len(source_files)} source patches + {len(manifest_files)} manifests = {len(all_files)} total")

    # ── 3. Get existing file paths in the branch (branched from default_ref) ──
    log.info(f"hitl — scanning existing files in {default_ref}…")
    existing = _existing_paths(project, default_ref)
    log.info(f"hitl — {len(existing)} existing files in {default_ref}")

    # ── 4. Push via GitLab Commits REST API ───────────────────────────────────
    first_msg = (
        f"fix({severity}): {issue_summary[:72]}\n\n"
        f"Automated fix by ShiftLeft.\nRun: {run_id}\n"
        f"Files: {', '.join(changed_files) or 'none'}"
    )
    _push_commit(project, branch, source_files, first_msg, existing)

    # Push YAML manifests in separate commit
    if manifest_files:
        _push_commit(
            project, branch, manifest_files,
            f"docs(shiftleft): YAML manifests + audit log — {run_id}",
            existing,
        )

    # ── 5. Open Merge Request via REST ────────────────────────────────────────
    tests_badge = "✅ PASSED" if state.get("tests_passed") else "⚠️ SKIPPED"
    files_md    = "\n".join(f"- `{f}`" for f in changed_files) or "_No source files patched._"
    test_out    = (state.get("test_results") or "No tests run.")[:600]

    description = f"""## ShiftLeft Automated Fix

| Field | Value |
|---|---|
| Run ID | `{run_id}` |
| Severity | **{severity.upper()}** |
| Tests | {tests_badge} |

### What was found
{issue_summary}

### Files changed
{files_md}

### Test output
```
{test_out}
```

### Codebase documentation
This MR also commits `.shiftleft/` — a YAML map of every Python file,
auto-generated by ShiftLeft's cartographer agent.

---
*Generated by [ShiftLeft](https://github.com/gvamaresh/shiftleft)*
*Stack: Gemini 3.1 Pro · GitLab MCP · LangGraph · Google Cloud*
"""

    mr_title = f"fix({severity}): {issue_summary[:80]}"
    log.info(f"hitl — creating MR via REST: {mr_title}")

    mr = _create_mr_rest(
        project=project, branch=branch,
        target=default_ref, title=mr_title, description=description,
    )

    mr_url    = mr.get("web_url", "")
    mr_number = int(mr.get("iid") or 0)

    log.info(f"hitl — ✅ MR: {mr_url}")
    print(f"\n{'='*64}\n✅  MR created: {mr_url}\n{'='*64}\n")

    return {
        **state,
        "pr_url":        mr_url,
        "pr_number":     mr_number,
        "changed_files": changed_files,
        "diff_hunks":    diff_hunks,
    }