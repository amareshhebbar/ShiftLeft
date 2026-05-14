"""
Triage agent — reads the file map and uses Gemini to identify
the single highest-impact issue to fix in this run.
"""

import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from core.state import ShiftLeftState
from utils.config import GEMINI_API_KEY, GEMINI_MODEL
from utils.logger import get_logger

log = get_logger(__name__)

_llm = ChatGoogleGenerativeAI(
    model=GEMINI_MODEL,
    google_api_key=GEMINI_API_KEY,
    temperature=0.1,
)

SYSTEM = """You are a senior software engineer performing automated code triage.
You will receive a structured map of a Python repository — every file, its purpose,
and every public function (with its signature and docstring).

Your job: identify the single most impactful code quality issue present.
Focus on: bugs, missing error handling, security vulnerabilities, broken logic,
missing type annotations on public APIs, or dangerously untested code paths.

Respond ONLY with valid JSON matching this schema exactly:
{
  "issue_summary": "one paragraph, specific, actionable",
  "target_files":  ["path/to/file.py", ...],
  "severity":      "critical|high|medium|low",
  "rationale":     "why this issue matters more than others"
}
Do not include markdown fences or any text outside the JSON object."""


def _build_prompt(file_map: dict) -> str:
    lines = []
    for rel_path, meta in list(file_map.items())[:40]:  # cap at 40 files
        lines.append(f"\n## {rel_path}")
        lines.append(f"Purpose: {meta.get('purpose', '(unknown)')}")
        for fn in meta.get("functions", [])[:10]:
            sig = f"  fn {fn['name']}({', '.join(fn['takes'])}) -> {fn['returns']}"
            lines.append(sig)
            lines.append(f"     does: {fn['does']}")
        for cls in meta.get("classes", [])[:5]:
            lines.append(f"  class {cls['name']}: {cls['does']}")
    return "\n".join(lines)


def triage_node(state: ShiftLeftState) -> ShiftLeftState:
    file_map = state.get("file_map") or {}
    if not file_map:
        log.warning("[triage] empty file_map — skipping")
        return {
            **state,
            "issue_summary": "No Python files found in repository.",
            "target_files":  [],
            "severity":      "low",
        }

    prompt = _build_prompt(file_map)
    log.info(f"[triage] sending {len(file_map)} files to Gemini for triage")

    response = _llm.invoke([
        SystemMessage(content=SYSTEM),
        HumanMessage(content=f"Repository map:\n{prompt}"),
    ])

    try:
        data = json.loads(response.content)
    except json.JSONDecodeError:
        # Gemini occasionally wraps output in ```json — strip and retry
        import re
        cleaned = re.sub(r"```(?:json)?|```", "", response.content).strip()
        data    = json.loads(cleaned)

    log.info(f"[triage] severity={data['severity']}, "
             f"files={data['target_files']}, "
             f"summary={data['issue_summary'][:80]}…")

    return {
        **state,
        "issue_summary": data["issue_summary"],
        "target_files":  data["target_files"],
        "severity":      data["severity"],
    }