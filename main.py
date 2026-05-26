"""
main.py — ShiftLeft CLI entry point.

Usage:
  python main.py                          # run once against GITLAB_TARGET_PROJECT
  python main.py --repo user/myrepo       # run once against a specific project
  python main.py --serve                  # start the Cloud Run webhook server

Vertex AI authentication (local):
  gcloud auth application-default login
  export GCP_PROJECT_ID=your-project-id
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone

# Load .env before anything else
_env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env_path):
    for _line in open(_env_path).read().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip().strip('"'))

from core.graph import shiftleft_app
from core.state import ShiftLeftState
from utils.config import GITLAB_TARGET_PROJECT
from utils.logger import get_logger
from utils.tracing import init_tracing

log = get_logger(__name__)


def run_once(gitlab_project: str, trigger: str = "manual") -> dict:
    # Initialise Arize Phoenix tracing (no-op if not configured)
    init_tracing()

    run_id = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    initial_state: ShiftLeftState = {
        "run_id":            run_id,
        "repo_url":          f"https://gitlab.com/{gitlab_project}",
        "trigger_source":    trigger,
        "gitlab_project_id": gitlab_project,
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

    log.info(f"ShiftLeft — run_id={run_id}  project={gitlab_project}  trigger={trigger}")
    result = shiftleft_app.invoke(initial_state)

    pr_url = result.get("pr_url", "")
    if pr_url:
        log.info(f"✅ Done — MR: {pr_url}")
        print(f"\n✅ Done — MR: {pr_url}\n")
    else:
        log.warning("⚠ Run completed but no MR was created.")
        print("\n⚠ Run completed but no MR URL in state — check logs above.\n")

    return result


def serve() -> None:
    """Start the FastAPI webhook server for Cloud Run."""
    import uvicorn
    from cloud.web_hook import app
    log.info("Starting ShiftLeft webhook server on :8080")
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ShiftLeft — Autonomous GitLab Bug Fixer")
    parser.add_argument("--serve", action="store_true", help="Run webhook server (Cloud Run mode)")
    parser.add_argument("--repo", default=None, help="GitLab project path, e.g. myuser/myrepo")
    args = parser.parse_args()

    if args.serve:
        serve()
    else:
        target = args.repo or GITLAB_TARGET_PROJECT
        if not target:
            print("❌ Set GITLAB_TARGET_PROJECT in .env or pass --repo myuser/myrepo")
            raise SystemExit(1)
        run_once(target)