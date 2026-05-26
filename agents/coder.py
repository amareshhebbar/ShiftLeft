from __future__ import annotations

import difflib
import re
from typing import Any, Dict, List, Optional

from core.state import PatchFile, ShiftLeftState
from utils.llm import generate
from utils.logger import get_logger

log = get_logger(__name__)


# ── Language detection ────────────────────────────────────────────────────────

_EXT_LANG = {
    ".py":   "python",
    ".js":   "javascript",
    ".ts":   "typescript",
    ".jsx":  "javascript",
    ".tsx":  "typescript",
    ".go":   "go",
    ".rb":   "ruby",
    ".java": "java",
    ".rs":   "rust",
    ".sh":   "bash",
}


def _detect_lang(filepath: str) -> str:
    for ext, lang in _EXT_LANG.items():
        if filepath.endswith(ext):
            return lang
    return "text"


# ── Prompt ────────────────────────────────────────────────────────────────────

_CODER_PROMPT = """\
You are an expert software engineer. Fix exactly one specific bug in the file below.

## Bug report
Severity  : {severity}
File      : {filepath}
Language  : {language}
Summary   : {issue_summary}

## Current file content
```{language}
{original_content}
```
{extra_context}
## Instructions
- Fix ONLY the described bug. Do not refactor or change anything else.
- Return the COMPLETE fixed file (not a diff, not a snippet — the ENTIRE file).
- Wrap the entire file in a single ```{language} ... ``` block.
- Add any new import/require at the top, grouped with existing ones.
- Do NOT add any explanation outside the code block.
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_code(response_text: str, original: str, lang: str) -> str:
    """Extract the code block from the LLM response."""
    patterns = [
        rf"```{lang}\s*\n(.*?)```",
        r"```\w*\s*\n(.*?)```",
    ]
    for pat in patterns:
        m = re.search(pat, response_text, re.DOTALL)
        if m:
            code = m.group(1)
            # Sanity: must be at least 30% the size of original
            if len(code.strip()) >= len(original.strip()) * 0.3:
                return code
    # Last resort: if response looks like code, use it directly
    stripped = response_text.strip()
    if any(stripped.startswith(kw) for kw in
           ("import ", "from ", "def ", "class ", "#!", "package ", "func ", "const ", "var ")):
        return stripped

    log.warning("coder — could not extract code block; using original unchanged")
    return original


def _unified_diff(original: str, patched: str, filepath: str) -> str:
    return "".join(difflib.unified_diff(
        original.splitlines(keepends=True),
        patched.splitlines(keepends=True),
        fromfile=f"a/{filepath}",
        tofile=f"b/{filepath}",
        lineterm="",
    ))


# ── Agent entry point ─────────────────────────────────────────────────────────

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

    patches: List[PatchFile] = []

    for filepath in target_files:
        info = file_map.get(filepath)
        if not info:
            log.warning(f"coder — {filepath} not in file_map, skipping")
            continue

        original_content = info.get("raw_content", "")
        if not original_content.strip():
            log.warning(f"coder — {filepath} has empty raw_content, skipping")
            continue

        language = _detect_lang(filepath)

        # Build extra context for retry iterations
        extra_context = ""
        if iteration > 1:
            for p in prev_patches:
                if p.get("file_path") == filepath:
                    extra_context = (
                        f"\n## ⚠️ Previous fix FAILED the auditor\n"
                        f"The diff that was rejected:\n"
                        f"```diff\n{p.get('diff','')[:600]}\n```\n"
                        f"Try a fundamentally different approach.\n\n"
                    )
                    break

        prompt = _CODER_PROMPT.format(
            severity=severity,
            filepath=filepath,
            language=language,
            issue_summary=issue_summary,
            original_content=original_content[:12_000],
            extra_context=extra_context,
        )

        log.info(
            f"coder — calling Gemini (Vertex AI) for {filepath} "
            f"({len(original_content)} chars, lang={language})"
        )
        try:
            raw = generate(prompt, temperature=0.15, max_tokens=8192)
        except Exception as exc:
            log.error(f"coder — LLM call failed for {filepath}: {exc}")
            raise

        patched_content = _extract_code(raw, original_content, language)
        diff = _unified_diff(original_content, patched_content, filepath)

        if not diff.strip():
            log.warning(
                f"coder — patch for {filepath} produced no diff "
                "(LLM returned the same file — will retry if iterations remain)"
            )
        else:
            changed_lines = sum(1 for l in diff.splitlines() if l.startswith(("+", "-")) and not l.startswith(("+++", "---")))
            log.info(f"coder — patch for {filepath}: {changed_lines} lines changed")

        patches.append({
            "file_path":        filepath,
            "original_content": original_content,
            "patched_content":  patched_content,
            "diff":             diff,
        })

    return {**state, "patches": patches, "iteration": iteration}