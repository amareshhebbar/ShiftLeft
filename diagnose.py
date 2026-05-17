import os, sys, time
from pathlib import Path

GRN = "\033[92m"; RED = "\033[91m"; YLW = "\033[93m"; BLU = "\033[94m"; RST = "\033[0m"
ok  = lambda s: print(f"  {GRN}✅ {s}{RST}")
err = lambda s: print(f"  {RED}❌ {s}{RST}")
hdr = lambda s: print(f"\n{BLU}{'─'*60}\n  {s}\n{'─'*60}{RST}")

PASS = True

def check(label, fn):
    global PASS
    try:
        result = fn()
        suffix = f" → {result}" if result not in (None, True, "ok") else ""
        ok(f"{label}{suffix}")
        return result
    except Exception as e:
        err(f"{label}\n    {type(e).__name__}: {e}")
        PASS = False
        return None

# ── 1. ENV ────────────────────────────────────────────────────────────────────
hdr("1 / 7 — Environment & .env")
env_path = Path(".env")
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"'))
    ok(".env loaded")
else:
    err(".env file not found"); sys.exit(1)

REQUIRED = {
    "GEMINI_API_KEY":        lambda v: v.startswith("AIza"),
    "GEMINI_MODEL":          lambda v: v == "gemini-3.1-flash-lite",
    "GITLAB_TOKEN":          lambda v: v.startswith("glpat-"),
    "GITLAB_URL":            lambda v: v == "https://gitlab.com",
    "GITLAB_TARGET_PROJECT": lambda v: "/" in v and "https" not in v,
}
all_env_ok = True
for var, validator in REQUIRED.items():
    val = os.environ.get(var, "")
    display = val[:30] + "..." if len(val) > 30 else val
    if not val:
        err(f"{var} — MISSING"); all_env_ok = False
    elif not validator(val):
        err(f"{var} = '{display}' — looks wrong"); all_env_ok = False
    else:
        ok(f"{var} = '{display}'")
if not all_env_ok:
    print(f"\n{RED}Fix env vars above before continuing.{RST}"); sys.exit(1)

# ── 2. FILES ──────────────────────────────────────────────────────────────────
hdr("2 / 7 — Repository hygiene")
check("LICENSE", lambda: Path("LICENSE").exists())
check("requirements.txt", lambda: Path("requirements.txt").exists())
check("main.py", lambda: Path("main.py").exists())

# ── 3. IMPORTS ────────────────────────────────────────────────────────────────
hdr("3 / 7 — Python imports")
check("httpx",                  lambda: __import__("httpx") and "ok")
check("langgraph",              lambda: __import__("langgraph") and "ok")
check("google.generativeai",    lambda: __import__("google.generativeai") and "ok")
check("langchain_google_genai", lambda: __import__("langchain_google_genai") and "ok")
check("streamlit",              lambda: __import__("streamlit") and "ok")
check("fastapi",                lambda: __import__("fastapi") and "ok")
check("yaml",                   lambda: __import__("yaml") and "ok")
check("utils.config",           lambda: __import__("utils.config") and "ok")
check("tools.gitlab_mcp_tools", lambda: __import__("tools.gitlab_mcp_tools") and "ok")
check("core.state → ShiftLeftState", lambda: (
    __import__("core.state", fromlist=["ShiftLeftState"]).ShiftLeftState and "ok"))
check("core.state → PatchFile", lambda: (
    __import__("core.state", fromlist=["PatchFile"]).PatchFile and "ok"))
check("core.state → TestResult", lambda: (
    __import__("core.state", fromlist=["TestResult"]).TestResult and "ok"))
check("agents.cartographer",    lambda: __import__("agents.cartographer") and "ok")
check("agents.triage",          lambda: __import__("agents.triage") and "ok")
check("agents.coder",           lambda: __import__("agents.coder") and "ok")
check("agents.auditor",         lambda: __import__("agents.auditor") and "ok")
check("agents.hitl",            lambda: __import__("agents.hitl") and "ok")

# ── 4. GitLab MCP (subprocess) ────────────────────────────────────────────────
hdr("4 / 7 — GitLab MCP (subprocess stdio)")

import shutil
npx_path = shutil.which("npx")
if not npx_path:
    err("npx not found — install Node.js: https://nodejs.org"); sys.exit(1)
ok(f"npx found → {npx_path}")

try:
    from tools.gitlab_mcp_tools import (
        list_available_tools, list_issues, get_repository_tree, get_file_content,
    )
except Exception as e:
    err(f"Cannot import gitlab_mcp_tools: {e}"); sys.exit(1)

PROJECT = os.environ["GITLAB_TARGET_PROJECT"]
print(f"  {YLW}Starting MCP subprocess — 5-15s on first run...{RST}")
t0 = time.time()

tools_result = check("tools/list (MCP handshake)", lambda: (
    lambda tools: f"{len(tools)} tools: {tools[:5]}"
)(list_available_tools()))

if tools_result is None:
    print(f"""
{RED}MCP handshake FAILED.{RST}
Run this manually to see the raw error:
  GITLAB_PERSONAL_ACCESS_TOKEN={os.environ['GITLAB_TOKEN']} npx -y @modelcontextprotocol/server-gitlab
{YLW}Paste output into chat — I'll fix it immediately.{RST}
"""); sys.exit(1)

print(f"  {GRN}MCP ready in {time.time()-t0:.1f}s{RST}")

check("list_issues via MCP", lambda: (
    lambda issues: f"{len(issues)} open issues"
)(list_issues(project=PROJECT, state="opened", per_page=10)))

check("get_repository_tree (REST)", lambda: (
    lambda tree: f"{len(tree)} items, {sum(1 for f in tree if str(f.get('path','')).endswith('.py'))} .py files"
)(get_repository_tree(project=PROJECT, recursive=True)))

def _test_file_read():
    tree = get_repository_tree(project=PROJECT, recursive=True)
    py_files = [f["path"] for f in tree if isinstance(f, dict) and str(f.get("path","")).endswith(".py")]
    if not py_files:
        raise RuntimeError("No Python files in tree")
    for fp in py_files[:5]:
        try:
            c = get_file_content(fp, project=PROJECT)
            if c and len(c) > 20:
                return f"{fp} — {len(c)} chars"
        except Exception:
            continue
    raise RuntimeError("Could not read any Python file")
check("get_file_content (MCP→REST fallback)", _test_file_read)

# ── 5. GEMINI ─────────────────────────────────────────────────────────────────
hdr("5 / 7 — Gemini API")
def _test_gemini():
    import google.generativeai as genai
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    resp = genai.GenerativeModel(os.environ["GEMINI_MODEL"]).generate_content(
        "Reply with exactly: SHIFTLEFT_OK")
    if "SHIFTLEFT_OK" not in resp.text:
        raise RuntimeError(f"Bad response: {resp.text[:80]}")
    return "Gemini 2.5 Flash ✓"
check("Gemini round-trip", _test_gemini)

# ── 6. STATE SCHEMA ───────────────────────────────────────────────────────────
hdr("6 / 7 — State schema")
def _test_state():
    import typing
    from core.state import ShiftLeftState
    hints = typing.get_type_hints(ShiftLeftState)
    missing = [f for f in [
        "run_id","gitlab_project_id","open_issues","file_map","yaml_map",
        "branch_name","issue_summary","target_files","severity",
        "patches","iteration","test_results","tests_passed",
        "pr_url","pr_number","diff_hunks","changed_files",
    ] if f not in hints]
    if missing: raise KeyError(f"Missing: {missing}")
    return f"{len(hints)} fields ✓"
check("ShiftLeftState fields", _test_state)

# ── 7. AGENT SIGNATURES ───────────────────────────────────────────────────────
hdr("7 / 7 — Agent signatures")
def _sig(mod, fn):
    import importlib, inspect
    return f"{fn}({list(inspect.signature(getattr(importlib.import_module(mod), fn)).parameters)})"
check("cartographer", lambda: _sig("agents.cartographer", "cartographer"))
check("triage",       lambda: _sig("agents.triage",       "triage"))
check("coder",        lambda: _sig("agents.coder",        "coder"))
check("auditor",      lambda: _sig("agents.auditor",      "auditor"))
check("hitl",         lambda: _sig("agents.hitl",         "hitl"))

# ── SUMMARY ───────────────────────────────────────────────────────────────────
print(f"\n{'═'*60}")
if PASS:
    print(f"{GRN}  ALL CHECKS PASSED ✅  →  python main.py{RST}")
else:
    print(f"{RED}  SOME CHECKS FAILED — paste output into chat.{RST}")
print(f"{'═'*60}\n")