from __future__ import annotations

import difflib
import re
import warnings
from typing import Any, Dict, List

warnings.filterwarnings("ignore", category=FutureWarning, module="google")
import google.generativeai as genai

from core.state import PatchFile, ShiftLeftState
from utils.config import GEMINI_API_KEY, GEMINI_MODEL
from utils.logger import get_logger

log = get_logger(__name__)

genai.configure(api_key=GEMINI_API_KEY)

_CODER_PROMPT = """\
You are an expert Python engineer. Your task is to fix one specific bug in a file.

## Bug report
Severity : {severity}
File     : {filepath}
Summary  : {issue_summary}

## Current file content
```python
{original_content}
```

## Instructions
- Fix ONLY the described bug. Touch nothing else.
- Return the COMPLETE fixed file (not a diff, not a snippet — the whole file).
- Wrap the entire file in a single ```python ... ``` block.
- If the fix requires a new import, add it at the top with the other imports.
- Do NOT add any explanation outside the code block.
"""


def _extract_code(response_text: str, original: str) -> str:
    """Pull the Python code block out of Gemini's response."""
    patterns = [
        r"```python\s*\n(.*?)```",
        r"```\s*\n(.*?)```",
    ]
    for pat in patterns:
        m = re.search(pat, response_text, re.DOTALL)
        if m:
            code = m.group(1)
            if len(code.strip()) > len(original) * 0.3:
                return code
    stripped = response_text.strip()
    if stripped.startswith(("import ", "from ", "def ", "class ", "#")):
        return stripped
    log.warning("coder — could not extract code block from Gemini response; using original")
    return original


def _unified_diff(original: str, patched: str, filepath: str) -> str:
    original_lines = original.splitlines(keepends=True)
    patched_lines  = patched.splitlines(keepends=True)
    diff = difflib.unified_diff(
        original_lines, patched_lines,
        fromfile=f"a/{filepath}", tofile=f"b/{filepath}",
        lineterm="",
    )
    return "".join(diff)


def coder(state: ShiftLeftState) -> ShiftLeftState:
    target_files  = state.get("target_files") or []
    file_map      = state.get("file_map") or {}
    issue_summary = state.get("issue_summary", "")
    severity      = state.get("severity", "medium")
    iteration     = (state.get("iteration") or 0) + 1
    prev_patches  = state.get("patches") or []

    log.info(f"coder — iteration {iteration}, targets: {target_files}")

    if not target_files:
        log.warning("coder — no target_files in state")
        return {**state, "patches": [], "iteration": iteration}

    model   = genai.GenerativeModel(GEMINI_MODEL)
    patches: List[PatchFile] = []

    for filepath in target_files:
        info = file_map.get(filepath)
        if not info:
            log.warning(f"coder — {filepath} not in file_map, skipping")
            continue

        original_content = info.get("raw_content", "")
        if not original_content.strip():
            log.warning(f"coder — {filepath} has empty raw_content")
            continue
        extra_context = ""
        if iteration > 1 and prev_patches:
            for p in prev_patches:
                if p.get("file_path") == filepath:
                    extra_context = (
                        f"\n\nNOTE: Your previous fix failed the auditor. "
                        f"The failed patch diff was:\n{p.get('diff','')[:500]}\n"
                        f"Try a different approach."
                    )

        prompt = _CODER_PROMPT.format(
            severity=severity,
            filepath=filepath,
            issue_summary=issue_summary,
            original_content=original_content[:10_000],  
        ) + extra_context

        log.info(f"coder — calling Gemini for {filepath} ({len(original_content)} chars)")
        try:
            resp = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.15,
                    max_output_tokens=8192,
                ),
            )
            raw = resp.text
        except Exception as exc:
            log.error(f"coder — Gemini call failed for {filepath}: {exc}")
            raise

        patched_content = _extract_code(raw, original_content)
        diff            = _unified_diff(original_content, patched_content, filepath)

        if not diff.strip():
            log.warning(f"coder — patch for {filepath} produced no diff (Gemini may have returned the same file)")
        else:
            log.info(f"coder — patch for {filepath}: {diff.count(chr(10))} diff lines")

        patches.append({
            "file_path":        filepath,
            "original_content": original_content,
            "patched_content":  patched_content,
            "diff":             diff,
        })

    return {
        **state,
        "patches":   patches,
        "iteration": iteration,
    }