"""
ShiftLeftState — the single shared envelope that flows through
every LangGraph node. All fields are optional except repo_url and run_id
so the graph can be invoked with a minimal initial payload.
"""

from typing import TypedDict, Optional, List, Dict, Any


class PatchFile(TypedDict):
    filename: str       # repo-relative path, e.g. "agents/coder.py"
    content:  str       # full new file content (not a diff)
    reason:   str       # one-line explanation of what was changed


class TestResult(TypedDict):
    passed:   bool
    output:   str       # combined stdout + stderr from the test run
    duration: float     # seconds


class ShiftLeftState(TypedDict, total=False):
    # ── Inputs (set at graph invocation) ──────────────────────────────────
    repo_url:       str          # e.g. "https://github.com/owner/repo.git"
    run_id:         str          # e.g. "2026-05-14_143022"
    trigger_source: str          # "webhook" | "scheduler" | "manual"

    # ── Cartographer outputs ───────────────────────────────────────────────
    branch_name:    str          # e.g. "shiftleft/run-2026-05-14_143022"
    file_map:       Dict[str, Any]   # rel_path → ast analysis dict
    yaml_map:       Dict[str, str]   # rel_path → YAML file content string
    repo_local_path: str         # temp dir where repo was cloned

    # ── Triage outputs ─────────────────────────────────────────────────────
    issue_summary:  str          # one-paragraph description of the problem
    target_files:   List[str]    # files the coder should patch
    severity:       str          # "critical" | "high" | "medium" | "low"

    # ── Coder outputs ──────────────────────────────────────────────────────
    patches:        List[PatchFile]
    iteration:      int          # self-correction loop counter (max 3)

    # ── Auditor outputs ────────────────────────────────────────────────────
    test_results:   TestResult
    tests_passed:   bool

    # ── HITL outputs ───────────────────────────────────────────────────────
    pr_url:         str
    pr_number:      int
    diff_hunks:     Dict[str, str]   # filename → unified diff string
    changed_files:  List[str]