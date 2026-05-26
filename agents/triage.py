"""
agents/triage.py — Bug triage agent.

Sends the codebase map + open GitLab issues to Gemini (via Vertex AI)
and picks the single highest-severity bug to fix.
"""

from __future__ import annotations

import json
import textwrap
from typing import Any, Dict, List

from core.state import ShiftLeftState
from utils.llm import generate
from utils.logger import get_logger

log = get_logger(__name__)

SKIP_TARGET_PATTERNS = (
    "docs/", "tests/", "test_", "migrations/", ".shiftleft/",
    "setup.py", "conf.py", "conftest.py",
)


# ── Formatters ────────────────────────────────────────────────────────────────

def _fmt_issues(issues: List[Dict]) -> str:
    if not issues:
        return "No open issues — perform static analysis only."
    lines = []
    for i in issues[:10]:
        desc = textwrap.shorten((i.get("description") or "").strip(), 200, placeholder="…")
        lines.append(f"#{i.get('iid','?')}: {i.get('title','')}\n  {desc}")
    return "\n\n".join(lines)


def _fmt_file_map(file_map: Dict[str, Any]) -> str:
    lines = []
    for fp, info in file_map.items():
        if any(p in fp for p in SKIP_TARGET_PATTERNS):
            continue
        fns  = [f["name"] for f in info.get("functions", [])]
        cls  = [c["name"] for c in info.get("classes", [])]
        imps = info.get("imports", [])[:8]
        entry = (
            f"FILE: {fp}  ({info.get('loc', 0)} lines)\n"
            f"  imports:   {', '.join(imps) or 'none'}\n"
            f"  functions: {', '.join(fns) or 'none'}\n"
            f"  classes:   {', '.join(cls) or 'none'}"
        )
        if info.get("parse_error"):
            entry += f"\n  PARSE ERROR: {info['parse_error']}"
        lines.append(entry)
    return "\n".join(lines)


# ── Prompt ────────────────────────────────────────────────────────────────────

_PROMPT = """\
You are a principal engineer performing automated bug triage on a codebase.

## Open issues (user-reported)
{issues}

## Codebase map (docs/ and test files excluded)
{file_map}

## Task
Pick the SINGLE highest-impact bug. Priority order:
1. Matches an open issue AND is fixable in one file
2. Reliability: unhandled exceptions, missing error handling, crashes
3. Correctness: wrong logic, data loss, off-by-one errors

CRITICAL RULES:
- Do NOT target docs/, tests/, test_*, migrations/, setup.py, conf.py
- Target only production source files with meaningful logic
- The fix must require changing exactly ONE file

Return ONLY this JSON — no markdown, no extra text:
{{
  "severity": "critical|high|medium|low",
  "target_files": ["exactly/one/source_file.py"],
  "issue_summary": "One sentence max 100 chars describing the exact bug",
  "root_cause": "2 sentences explaining why this is a bug",
  "suggested_fix": "2 sentences on how to fix it",
  "related_issue_iid": null
}}
"""


# ── Agent entry point ─────────────────────────────────────────────────────────

def triage(state: ShiftLeftState) -> ShiftLeftState:
    file_map    = state.get("file_map") or {}
    open_issues = state.get("open_issues") or []

    if not file_map:
        log.warning("triage — file_map empty, nothing to triage")
        return {**state, "issue_summary": "No files to analyze",
                "target_files": [], "severity": "low"}

    code_file_map = {
        fp: info for fp, info in file_map.items()
        if not any(p in fp for p in SKIP_TARGET_PATTERNS)
    }
    if not code_file_map:
        code_file_map = file_map

    log.info(
        f"triage — {len(code_file_map)} code files + {len(open_issues)} issues → Gemini (Vertex AI)"
    )

    prompt = _PROMPT.format(
        issues=_fmt_issues(open_issues),
        file_map=_fmt_file_map(code_file_map),
    )

    try:
        raw = generate(prompt, temperature=0.1, max_tokens=4096)
    except Exception as exc:
        log.error(f"triage — LLM call failed: {exc}")
        raise

    # Strip markdown fences if the model wraps the JSON
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1].lstrip("json").strip() if len(parts) > 1 else raw

    try:
        result: Dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError:
        log.error(f"triage — invalid JSON from LLM (len={len(raw)}):\n{raw[:400]}")
        best = max(code_file_map.items(), key=lambda kv: kv[1].get("loc", 0))
        result = {
            "severity":          "medium",
            "target_files":      [best[0]],
            "issue_summary":     f"Potential reliability issue in {best[0]}",
            "root_cause":        "Automated triage could not parse LLM JSON response.",
            "suggested_fix":     "Review the file manually.",
            "related_issue_iid": None,
        }

    severity     = result.get("severity", "medium")
    target_files = result.get("target_files") or []
    summary      = result.get("issue_summary", "")

    # Validate that target files actually exist in the file map
    valid = [f for f in target_files if f in file_map]
    if not valid:
        # Try basename matching (LLM sometimes drops the directory prefix)
        for candidate in target_files:
            base = candidate.split("/")[-1]
            for known in code_file_map:
                if known.split("/")[-1] == base:
                    valid.append(known)
                    break

    # Final fallback — pick the largest non-test code file
    if not valid:
        best = max(code_file_map.items(), key=lambda kv: kv[1].get("loc", 0))
        valid = [best[0]]
        log.warning(f"triage — LLM target {target_files!r} not in map; using {valid}")

    # Enforce skip patterns (never fix test/docs files)
    valid = [f for f in valid if not any(p in f for p in SKIP_TARGET_PATTERNS)]
    if not valid:
        best = max(code_file_map.items(), key=lambda kv: kv[1].get("loc", 0))
        valid = [best[0]]

    log.info(f"triage — severity={severity}  target={valid}  summary={summary!r}")
    return {**state, "issue_summary": summary, "target_files": valid, "severity": severity}