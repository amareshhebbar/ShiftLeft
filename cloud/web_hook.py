import hmac
import hashlib
import json
import shutil
from datetime import datetime, timezone

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from core.graph  import shiftleft_app
from core.state  import ShiftLeftState
from utils.config import WEBHOOK_SECRET, GITHUB_TARGET_REPO
from utils.logger import get_logger

log = get_logger(__name__)
app = FastAPI(title="ShiftLeft Webhook Server", version="1.0.0")


def _verify_github_sig(payload: bytes, sig_header: str) -> bool:
    if not sig_header or not sig_header.startswith("sha256="):
        return False
    mac = hmac.new(WEBHOOK_SECRET.encode(), payload, hashlib.sha256)
    expected = "sha256=" + mac.hexdigest()
    return hmac.compare_digest(expected, sig_header)


def _make_initial_state(repo_url: str, trigger: str) -> ShiftLeftState:
    run_id = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    return ShiftLeftState(
        repo_url=repo_url,
        run_id=run_id,
        trigger_source=trigger,
        branch_name=f"shiftleft/run-{run_id}",
        iteration=0,
        tests_passed=False,
    )


def _run_and_cleanup(state: ShiftLeftState) -> None:
    try:
        result = shiftleft_app.invoke(state)
        pr_url = result.get("pr_url")
        log.info(f"[webhook] run {state['run_id']} complete — PR: {pr_url}")
    except Exception as e:
        log.error(f"[webhook] run {state['run_id']} failed: {e}", exc_info=True)
    finally:
        repo_path = state.get("repo_local_path")
        if repo_path:
            shutil.rmtree(repo_path, ignore_errors=True)


@app.get("/health")
def health():
    return {"status": "ok", "service": "shiftleft"}


@app.post("/webhook/github")
async def github_webhook(request: Request, background: BackgroundTasks):
    payload = await request.body()
    sig     = request.headers.get("X-Hub-Signature-256", "")

    if not _verify_github_sig(payload, sig):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")

    event = request.headers.get("X-GitHub-Event", "")
    data  = json.loads(payload)
    if event != "push":
        return JSONResponse({"skipped": True, "reason": f"event={event}"})
    if not data.get("ref", "").endswith("/main"):
        return JSONResponse({"skipped": True, "reason": "not main branch"})

    repo_url = data["repository"]["clone_url"]
    state    = _make_initial_state(repo_url, "webhook:push")
    background.add_task(_run_and_cleanup, state)
    return JSONResponse({"queued": True, "run_id": state["run_id"]})


@app.post("/webhook/scheduler")
async def scheduler_trigger(request: Request, background: BackgroundTasks):
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass

    repo_url = body.get("repo_url") or \
               f"https://github.com/{GITHUB_TARGET_REPO}.git"
    trigger  = body.get("source", "scheduler")
    state    = _make_initial_state(repo_url, trigger)
    background.add_task(_run_and_cleanup, state)
    return JSONResponse({"queued": True, "run_id": state["run_id"]})