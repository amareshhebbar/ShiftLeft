from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any, Dict

# ── Colour helpers ────────────────────────────────────────────────────────────
GRN = "\033[92m"; RED = "\033[91m"; YLW = "\033[93m"
BLU = "\033[94m"; CYN = "\033[96m"; RST = "\033[0m"; BLD = "\033[1m"

def hdr(title: str, char: str = "═") -> None:
    width = 64
    print(f"\n{BLU}{char * width}{RST}")
    print(f"{BLD}{BLU}  {title}{RST}")
    print(f"{BLU}{char * width}{RST}")

def step(n: int, total: int, label: str) -> None:
    print(f"\n{CYN}[{n}/{total}] {label}{RST}")

def ok(msg: str)  -> None: print(f"  {GRN}✅ {msg}{RST}")
def err(msg: str) -> None: print(f"  {RED}❌ {msg}{RST}")
def inf(msg: str) -> None: print(f"  {YLW}ℹ  {msg}{RST}")

def _dump(label: str, val: Any, max_chars: int = 400) -> None:
    s = str(val)
    if len(s) > max_chars:
        s = s[:max_chars] + " …[truncated]"
    print(f"    {YLW}{label}:{RST} {s}")


# ── Load .env ─────────────────────────────────────────────────────────────────
import os
from pathlib import Path

env_path = Path(".env")
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"'))


# ── Args ──────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--issues", action="store_true",
                    help="Only create demo issues then exit")
parser.add_argument("--step", choices=["carto","triage","coder","auditor","hitl"],
                    help="Stop after this step")
parser.add_argument("--no-issues", action="store_true",
                    help="Skip issue creation")
args = parser.parse_args()


# ── Step 0: Create demo issues ────────────────────────────────────────────────
hdr("STEP 0 — Create demo GitLab issues (idempotent)")

import httpx as _httpx
from tools.gitlab_mcp_tools import list_issues

def create_issue(title, description, labels=None, project=None):
    from utils.config import GITLAB_TOKEN, GITLAB_URL, GITLAB_TARGET_PROJECT
    proj = project or GITLAB_TARGET_PROJECT
    enc  = proj.replace("/", "%2F")
    resp = _httpx.post(
        f"{GITLAB_URL}/api/v4/projects/{enc}/issues",
        headers={"PRIVATE-TOKEN": GITLAB_TOKEN},
        json={"title": title, "description": description,
              "labels": ",".join(labels) if labels else ""},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()

DEMO_ISSUES = [
    {
        "title":       "Missing error handling in http module when connection times out",
        "description": (
            "When making HTTP requests, the http module does not handle `ConnectionTimeout` "
            "or `ReadTimeout` exceptions. This causes unhandled exceptions that crash the "
            "client silently. Expected behaviour: retry with exponential backoff or raise "
            "a descriptive `GitlabHttpError`.\n\n"
            "Steps to reproduce:\n"
            "1. Set an extremely short timeout\n"
            "2. Call any API endpoint\n"
            "3. Observe unhandled TimeoutError"
        ),
        "labels": ["bug", "http", "shiftleft-demo"],
    },
    {
        "title":       "No retry logic for API rate limit responses (HTTP 429)",
        "description": (
            "The GitLab REST client does not handle HTTP 429 (Too Many Requests) responses. "
            "When the API rate limit is hit, the client raises an exception immediately "
            "instead of waiting for the `Retry-After` header value and retrying.\n\n"
            "This affects bulk operations like listing all projects for large accounts."
        ),
        "labels": ["bug", "api", "reliability", "shiftleft-demo"],
    },
    {
        "title":       "gl.projects.list() does not handle pagination edge cases",
        "description": (
            "When iterating over `gl.projects.list(all=True)`, the paginator can "
            "return duplicate items or miss the last page when total count is an exact "
            "multiple of `per_page`. The `x-next-page` header is not checked before "
            "issuing the next request, causing an extra empty API call.\n\n"
            "Reproducible with: per_page=100 and exactly 300 projects."
        ),
        "labels": ["bug", "pagination", "shiftleft-demo"],
    },
]

if not args.no_issues:
    try:
        existing = list_issues(state="opened", per_page=50)
        existing_titles = {i.get("title","") for i in existing}
        created = 0
        for issue in DEMO_ISSUES:
            if issue["title"] in existing_titles:
                inf(f"Issue already exists — skipping: {issue['title'][:60]}")
            else:
                result = create_issue(
                    title=issue["title"],
                    description=issue["description"],
                    labels=issue["labels"],
                )
                iid = result.get("iid") or result.get("id") or "?"
                ok(f"Created issue #{iid}: {issue['title'][:60]}")
                created += 1
                time.sleep(0.5) 
        if created == 0:
            inf("All 3 demo issues already exist — good.")
    except Exception as exc:
        err(f"Issue creation failed: {exc}")
        inf("Continuing without demo issues — pipeline will still work")
else:
    inf("Skipping issue creation (--no-issues)")

if args.issues:
    print(f"\n{GRN}✅ Issues created. Run without --issues for full pipeline.{RST}\n")
    sys.exit(0)


# ── Build initial state ───────────────────────────────────────────────────────
from core.state import ShiftLeftState

initial_state: ShiftLeftState = {
    "run_id":         "",
    "repo_url":       f"https://gitlab.com/{os.environ.get('GITLAB_TARGET_PROJECT','')}",
    "trigger_source": "test_pipeline.py",
    "gitlab_project_id": os.environ.get("GITLAB_TARGET_PROJECT", ""),
    "open_issues":    [],
    "branch_name":    "",
    "file_map":       {},
    "yaml_map":       {},
    "repo_local_path": "",
    "issue_summary":  "",
    "target_files":   [],
    "severity":       "medium",
    "patches":        [],
    "iteration":      0,
    "test_results":   "",
    "tests_passed":   False,
    "pr_url":         "",
    "pr_number":      0,
    "diff_hunks":     [],
    "changed_files":  [],
}

state = initial_state.copy()
t_start = time.time()


# ── Agent runner helper ───────────────────────────────────────────────────────
def run_agent(n: int, total: int, label: str, fn, current_state: Dict) -> Dict:
    step(n, total, label)
    t0 = time.time()
    try:
        new_state = fn(current_state)
        elapsed = time.time() - t0
        ok(f"{label} completed in {elapsed:.1f}s")
        return new_state
    except Exception as exc:
        elapsed = time.time() - t0
        err(f"{label} FAILED after {elapsed:.1f}s")
        err(f"  {type(exc).__name__}: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


TOTAL_STEPS = 5

# ── Step 1: Cartographer ──────────────────────────────────────────────────────
hdr("STEP 1 — Cartographer  (maps repo via GitLab MCP + REST)")

from agents.cartographer import cartographer
state = run_agent(1, TOTAL_STEPS, "cartographer", cartographer, state)

ok(f"run_id         = {state['run_id']}")
ok(f"branch_name    = {state['branch_name']}")
ok(f"files analyzed = {len(state['file_map'])}")
ok(f"YAML manifests = {len(state['yaml_map'])}")
ok(f"open issues    = {len(state['open_issues'])}")

print(f"\n  {CYN}Files mapped:{RST}")
for fp, info in list(state["file_map"].items())[:8]:
    fns = len(info.get("functions", []))
    cls = len(info.get("classes", []))
    loc = info.get("loc", 0)
    print(f"    {fp}  ({loc} loc, {fns} funcs, {cls} classes)")
if len(state["file_map"]) > 8:
    print(f"    … and {len(state['file_map']) - 8} more")

print(f"\n  {CYN}Open issues:{RST}")
for issue in state["open_issues"][:5]:
    print(f"    #{issue.get('iid','?')} {issue.get('title','')[:70]}")

if args.step == "carto":
    print(f"\n{GRN}Stopped at --step carto.{RST}\n"); sys.exit(0)


# ── Step 2: Triage ────────────────────────────────────────────────────────────
hdr("STEP 2 — Triage  (Gemini 2.5 Flash identifies the bug)")

from agents.triage import triage
state = run_agent(2, TOTAL_STEPS, "triage", triage, state)

ok(f"severity       = {state['severity'].upper()}")
ok(f"target_files   = {state['target_files']}")
_dump("issue_summary", state["issue_summary"])

if args.step == "triage":
    print(f"\n{GRN}Stopped at --step triage.{RST}\n"); sys.exit(0)


# ── Step 3: Coder ─────────────────────────────────────────────────────────────
hdr("STEP 3 — Coder  (Gemini 2.5 Flash writes the fix)")

from agents.coder import coder
state = run_agent(3, TOTAL_STEPS, "coder", coder, state)

ok(f"patches generated = {len(state['patches'])}")
for patch in state["patches"]:
    fp   = patch.get("file_path", "?")
    diff = patch.get("diff", "")
    lines_added   = diff.count("\n+") - diff.count("\n+++")
    lines_removed = diff.count("\n-") - diff.count("\n---")
    ok(f"  {fp}  (+{lines_added} / -{lines_removed} lines)")
    print()
    diff_preview = "\n".join(diff.splitlines()[:40])
    for line in diff_preview.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            print(f"    {GRN}{line}{RST}")
        elif line.startswith("-") and not line.startswith("---"):
            print(f"    {RED}{line}{RST}")
        else:
            print(f"    {line}")

if args.step == "coder":
    print(f"\n{GRN}Stopped at --step coder.{RST}\n"); sys.exit(0)


# ── Step 4: Auditor ───────────────────────────────────────────────────────────
hdr("STEP 4 — Auditor  (validates patch syntax)")

from agents.auditor import auditor

MAX_RETRIES = 3
for attempt in range(1, MAX_RETRIES + 1):
    state = run_agent(4, TOTAL_STEPS, f"auditor (attempt {attempt})", auditor, state)
    _dump("test_results", state["test_results"], max_chars=600)

    if state["tests_passed"]:
        ok("Auditor PASSED — proceeding to HITL")
        break
    else:
        err(f"Auditor FAILED on attempt {attempt}")
        if attempt < MAX_RETRIES:
            inf(f"Re-running coder (self-correction loop)…")
            state = run_agent(3, TOTAL_STEPS, f"coder (retry {attempt})", coder, state)
        else:
            err("Max retries reached — pushing patch anyway (auditor failed)")
            inf("The MR will be created but marked as needing review")
            state["tests_passed"] = False
            break

if args.step == "auditor":
    print(f"\n{GRN}Stopped at --step auditor.{RST}\n"); sys.exit(0)


# ── Step 5: HITL ─────────────────────────────────────────────────────────────
hdr("STEP 5 — HITL  (create branch → push → open MR via GitLab MCP)")

from agents.hitl import hitl
state = run_agent(5, TOTAL_STEPS, "hitl", hitl, state)


# ── Final summary ─────────────────────────────────────────────────────────────
elapsed_total = time.time() - t_start
hdr("✅  PIPELINE COMPLETE", char="═")

print(f"""
  {BLD}Run ID    :{RST} {state['run_id']}
  {BLD}Branch    :{RST} {state['branch_name']}
  {BLD}Files     :{RST} {', '.join(state.get('changed_files') or []) or 'none'}
  {BLD}Tests     :{RST} {'PASSED ✅' if state.get('tests_passed') else 'SKIPPED ⚠️'}
  {BLD}Duration  :{RST} {elapsed_total:.1f}s

  {BLD}{GRN}MR URL    : {state.get('pr_url','(not set)')} {RST}
""")

if state.get("pr_url"):
    print(f"{GRN}  Open the MR in your browser and review the diff.{RST}")
    print(f"{GRN}  You should also see a .shiftleft/ folder committed to the branch.{RST}")
else:
    print(f"{RED}  pr_url is empty — check hitl logs above for errors.{RST}")

print()