"""
Coder agent — generates patches for the files identified by triage.
Uses Gemini's full context window to read the target files in their
entirety and produce corrected versions.
"""

import os
import json
import re
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from core.state import ShiftLeftState, PatchFile
from utils.config import GEMINI_API_KEY, GEMINI_MODEL
from utils.logger import get_logger

log = get_logger(__name__)

_llm = ChatGoogleGenerativeAI(
    model=GEMINI_MODEL,
    google_api_key=GEMINI_API_KEY,
    temperature=0.15,
)

SYSTEM = """You are an expert Python engineer performing automated code repair.
You will receive:
  1. A description of the issue to fix.
  2. The full content of one or more files that need to be patched.
  3. (On retry) the test output from the previous attempt and what went wrong.

Produce corrected versions of the files.

Respond ONLY with a JSON array. Each element must match this schema exactly:
[
  {
    "filename": "agents/coder.py",
    "content":  "<complete new file content as a string>",
    "reason":   "one-line explanation of what was changed"
  }
]

Rules:
- Return the COMPLETE file content, not a diff.
- Do not truncate or abbreviate any code.
- Preserve all existing imports unless they are part of the bug.
- Do not add any text outside the JSON array.
- If a file does not need changes, do not include it in the response."""


def _read_file(repo_local_path: str, rel_path: str) -> str:
    abs_path = os.path.join(repo_local_path, rel_path)
    if not os.path.exists(abs_path):
        return f"# File not found: {rel_path}"
    with open(abs_path, "r", errors="replace") as f:
        return f.read()


def _build_prompt(state: ShiftLeftState) -> str:
    issue     = state.get("issue_summary", "")
    targets   = state.get("target_files", [])
    repo_path = state.get("repo_local_path", "")
    iteration = state.get("iteration", 0)
    previous  = state.get("test_results", {})

    parts = [f"Issue to fix:\n{issue}\n"]

    if iteration > 0 and previous:
        parts.append(
            f"Previous attempt failed (iteration {iteration}).\n"
            f"Test output:\n{previous.get('output', '')}\n"
            "Analyse the failures and produce a corrected patch.\n"
        )

    for rel_path in targets[:5]:   # cap at 5 files per run
        content = _read_file(repo_path, rel_path)
        parts.append(f"File: {rel_path}\n```python\n{content}\n```")

    return "\n\n".join(parts)


def coder_node(state: ShiftLeftState) -> ShiftLeftState:
    iteration = state.get("iteration", 0) + 1
    log.info(f"[coder] iteration {iteration}, "
             f"targets={state.get('target_files', [])}")

    prompt   = _build_prompt(state)
    response = _llm.invoke([
        SystemMessage(content=SYSTEM),
        HumanMessage(content=prompt),
    ])

    raw = response.content
    # strip markdown code fences if present
    raw = re.sub(r"```(?:json)?|```", "", raw).strip()

    try:
        patches_raw = json.loads(raw)
    except json.JSONDecodeError as e:
        log.error(f"[coder] JSON parse failed: {e}\nRaw:\n{raw[:500]}")
        # Return an empty patch list — auditor will report failure
        patches_raw = []

    patches: list[PatchFile] = [
        PatchFile(
            filename=p["filename"],
            content=p["content"],
            reason=p.get("reason", ""),
        )
        for p in patches_raw
    ]

    log.info(f"[coder] generated {len(patches)} patch(es)")
    return {
        **state,
        "patches":   patches,
        "iteration": iteration,
    }