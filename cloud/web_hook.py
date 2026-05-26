from __future__ import annotations

import hmac
import json
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from core.graph import shiftleft_app
from core.state import ShiftLeftState
from utils.config import WEBHOOK_SECRET, GITLAB_TARGET_PROJECT, GITLAB_URL
from utils.logger import get_logger
from utils.tracing import init_tracing

log = get_logger(__name__)

# Init Arize tracing at server startup (enables Arize prize-track observability)
init_tracing()

app = FastAPI(title="ShiftLeft Webhook Server", version="2.0.0")


# ── Token verification ────────────────────────────────────────────────────────

def _verify_gitlab_token(request: Request) -> bool:
    """
    GitLab sends the webhook token as the literal value in X-Gitlab-Token header.
    We compare in constant time to prevent timing attacks.
    """
    token = request.headers.get("X-Gitlab-Token", "")
    return hmac.compare_digest(token, WEBHOOK_SECRET)


# ── State factory ─────────────────────────────────────────────────────────────

def _make_state(project: str, trigger: str) -> ShiftLeftState:
    run_id = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    return ShiftLeftState(
        run_id=run_id,
        repo_url=f"{GITLAB_URL}/{project}",
        trigger_source=trigger,
        gitlab_project_id=project,
        open_issues=[],
        branch_name=f"shiftleft/run-{run_id}",
        file_map={},
        yaml_map={},
        repo_local_path="",
        issue_summary="",
        target_files=[],
        severity="medium",
        patches=[],
        iteration=0,
        test_results="",
        tests_passed=False,
        pr_url="",
        pr_number=0,
        diff_hunks=[],
        changed_files=[],
    )


# ── Background runner ─────────────────────────────────────────────────────────

def _run_pipeline(state: ShiftLeftState) -> None:
    """Run the full LangGraph pipeline in the background."""
    run_id = state["run_id"]
    log.info(f"[webhook] starting pipeline run_id={run_id} project={state.get('gitlab_project_id')}")
    try:
        result = shiftleft_app.invoke(state)
        pr_url = result.get("pr_url", "")
        log.info(f"[webhook] run {run_id} complete — MR: {pr_url}")
    except Exception as exc:
        log.error(f"[webhook] run {run_id} FAILED: {exc}", exc_info=True)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> Dict[str, Any]:
    """Cloud Run liveness probe."""
    return {
        "status":  "ok",
        "service": "shiftleft",
        "version": "2.0.0",
    }


@app.post("/webhook/gitlab/issue")
async def gitlab_issue_webhook(request: Request, background: BackgroundTasks) -> JSONResponse:
    """
    Triggered by GitLab when an issue event occurs.
    Starts a ShiftLeft run when:
      - A new issue is opened  AND it has the 'shiftleft' label, OR
      - The 'shiftleft' label is added to any existing issue.

    Configure in GitLab → Settings → Webhooks → Issues events.
    """
    if not _verify_gitlab_token(request):
        raise HTTPException(status_code=401, detail="Invalid X-Gitlab-Token")

    payload: Dict[str, Any] = await request.json()
    object_kind = payload.get("object_kind", "")

    if object_kind != "issue":
        return JSONResponse({"skipped": True, "reason": f"object_kind={object_kind}"})

    attrs  = payload.get("object_attributes", {})
    action = attrs.get("action", "")
    state  = attrs.get("state", "")

    # Only act on open/reopen/update — not close
    if action not in ("open", "reopen", "update"):
        return JSONResponse({"skipped": True, "reason": f"action={action}"})
    if state != "opened":
        return JSONResponse({"skipped": True, "reason": f"state={state}"})

    # Check for the 'shiftleft' label
    labels = payload.get("labels", [])
    label_names = [lbl.get("title", "").lower() for lbl in labels]
    changes = payload.get("changes", {})
    added_labels = [
        lbl.get("title", "").lower()
        for lbl in changes.get("labels", {}).get("previous", [])
    ]
    all_labels = set(label_names + added_labels)

    if "shiftleft" not in all_labels:
        return JSONResponse({
            "skipped": True,
            "reason": "no 'shiftleft' label — add label to trigger",
        })

    project = (
        payload.get("project", {}).get("path_with_namespace")
        or GITLAB_TARGET_PROJECT
    )

    log.info(
        f"[webhook] GitLab issue hook — project={project} "
        f"issue=#{attrs.get('iid')} action={action}"
    )

    pipeline_state = _make_state(project, trigger=f"gitlab:issue:{action}")
    background.add_task(_run_pipeline, pipeline_state)

    return JSONResponse({
        "queued":   True,
        "run_id":   pipeline_state["run_id"],
        "project":  project,
        "trigger":  f"issue #{attrs.get('iid')} labeled 'shiftleft'",
    })


@app.post("/webhook/gitlab/push")
async def gitlab_push_webhook(request: Request, background: BackgroundTasks) -> JSONResponse:
    """
    Triggered by GitLab push events.
    Starts a ShiftLeft run only on pushes to the default branch.
    Configure in GitLab → Settings → Webhooks → Push events.
    """
    if not _verify_gitlab_token(request):
        raise HTTPException(status_code=401, detail="Invalid X-Gitlab-Token")

    payload: Dict[str, Any] = await request.json()
    ref = payload.get("ref", "")

    # Only trigger on the default branch
    if not any(ref.endswith(b) for b in ("main", "master", "develop")):
        return JSONResponse({"skipped": True, "reason": f"ref={ref} is not default branch"})

    project = (
        payload.get("project", {}).get("path_with_namespace")
        or GITLAB_TARGET_PROJECT
    )

    log.info(f"[webhook] GitLab push hook — project={project} ref={ref}")

    pipeline_state = _make_state(project, trigger=f"gitlab:push:{ref}")
    background.add_task(_run_pipeline, pipeline_state)

    return JSONResponse({
        "queued":  True,
        "run_id":  pipeline_state["run_id"],
        "project": project,
        "ref":     ref,
    })


@app.post("/webhook/scheduler")
async def scheduler_trigger(request: Request, background: BackgroundTasks) -> JSONResponse:
    """
    Manual / Cloud Scheduler trigger.
    Body (optional JSON): { "project": "user/repo", "source": "scheduler" }
    """
    body: Dict[str, Any] = {}
    try:
        body = await request.json()
    except Exception:
        pass

    project = body.get("project") or body.get("repo") or GITLAB_TARGET_PROJECT
    trigger = body.get("source", "scheduler")

    if not project:
        raise HTTPException(status_code=400, detail="No project specified and GITLAB_TARGET_PROJECT not set.")

    log.info(f"[webhook] scheduler trigger — project={project}")
    pipeline_state = _make_state(project, trigger=trigger)
    background.add_task(_run_pipeline, pipeline_state)

    return JSONResponse({
        "queued":  True,
        "run_id":  pipeline_state["run_id"],
        "project": project,
    })