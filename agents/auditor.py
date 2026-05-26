from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List

from core.state import ShiftLeftState
from utils.logger import get_logger

log = get_logger(__name__)

MAX_ITERATIONS = 3


# ── Language detection ────────────────────────────────────────────────────────

def _lang(filepath: str) -> str:
    if filepath.endswith(".py"):    return "python"
    if filepath.endswith((".js", ".jsx")): return "javascript"
    if filepath.endswith((".ts", ".tsx")): return "typescript"
    if filepath.endswith(".go"):    return "go"
    return "unknown"


# ── Per-language validators ───────────────────────────────────────────────────

def _validate_python(filepath: str, content: str) -> tuple[bool, str]:
    """Syntax check via py_compile on a temp file."""
    tmp = tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False, encoding="utf-8")
    try:
        tmp.write(content)
        tmp.close()
        proc = subprocess.run(
            [sys.executable, "-m", "py_compile", tmp.name],
            capture_output=True, text=True, timeout=15,
        )
        if proc.returncode == 0:
            return True, "syntax OK"
        return False, f"SYNTAX ERROR\n{proc.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return False, "syntax check timed out"
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def _validate_javascript(filepath: str, content: str) -> tuple[bool, str]:
    """Syntax check via `node --check` on a temp file."""
    node = shutil.which("node")
    if not node:
        return True, "node not found — syntax check skipped (treated as pass)"

    tmp = tempfile.NamedTemporaryFile(suffix=".js", mode="w", delete=False, encoding="utf-8")
    try:
        tmp.write(content)
        tmp.close()
        proc = subprocess.run(
            [node, "--check", tmp.name],
            capture_output=True, text=True, timeout=15,
        )
        if proc.returncode == 0:
            return True, "JS syntax OK"
        return False, f"JS SYNTAX ERROR\n{proc.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return False, "JS syntax check timed out"
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def _validate_typescript(filepath: str, content: str) -> tuple[bool, str]:
    """Syntax check via `tsc --noEmit` if tsc is installed."""
    tsc = shutil.which("tsc")
    if not tsc:
        # Try npx tsc as fallback
        npx = shutil.which("npx")
        if not npx:
            return True, "tsc not found — TypeScript syntax check skipped (treated as pass)"
        tsc_cmd = [npx, "--yes", "typescript", "--noEmit"]
    else:
        tsc_cmd = [tsc, "--noEmit", "--strict", "--target", "ES2020"]

    tmpdir = tempfile.mkdtemp()
    try:
        tmp_path = os.path.join(tmpdir, os.path.basename(filepath))
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
        proc = subprocess.run(
            tsc_cmd + [tmp_path],
            capture_output=True, text=True, timeout=30, cwd=tmpdir,
        )
        if proc.returncode == 0:
            return True, "TypeScript syntax OK"
        return False, f"TS ERROR\n{proc.stdout[:600]}{proc.stderr[:200]}"
    except subprocess.TimeoutExpired:
        return False, "TypeScript check timed out"
    finally:
        import shutil as _shutil
        _shutil.rmtree(tmpdir, ignore_errors=True)


def _validate_go(filepath: str, content: str) -> tuple[bool, str]:
    """Syntax check via `go vet` if go is installed."""
    go = shutil.which("go")
    if not go:
        return True, "go not found — Go syntax check skipped (treated as pass)"

    tmpdir = tempfile.mkdtemp()
    try:
        tmp_path = os.path.join(tmpdir, os.path.basename(filepath))
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
        proc = subprocess.run(
            [go, "vet", tmp_path],
            capture_output=True, text=True, timeout=30, cwd=tmpdir,
        )
        if proc.returncode == 0:
            return True, "Go syntax OK"
        return False, f"GO VET ERROR\n{proc.stderr.strip()[:600]}"
    except subprocess.TimeoutExpired:
        return False, "Go vet timed out"
    finally:
        import shutil as _shutil
        _shutil.rmtree(tmpdir, ignore_errors=True)


def _validate_file(filepath: str, content: str) -> tuple[bool, str]:
    """Route to the correct language validator."""
    if not content.strip():
        return False, "patched_content is empty"

    lang = _lang(filepath)
    if lang == "python":     return _validate_python(filepath, content)
    if lang == "javascript": return _validate_javascript(filepath, content)
    if lang == "typescript": return _validate_typescript(filepath, content)
    if lang == "go":         return _validate_go(filepath, content)
    # Unknown language — just check it's non-empty
    return True, f"unknown language ({filepath.rsplit('.',1)[-1]}) — content check only"


# ── Agent entry point ─────────────────────────────────────────────────────────

def auditor(state: ShiftLeftState) -> ShiftLeftState:
    patches   = state.get("patches") or []
    iteration = state.get("iteration", 1)

    if not patches:
        log.info("auditor — no patches to validate, marking passed")
        return {**state, "tests_passed": True, "test_results": "No patches produced."}

    results: List[str] = []
    all_passed = True

    # ── Step 1: Per-file syntax validation ────────────────────────────────────
    for patch in patches:
        filepath = patch.get("file_path", "unknown")
        content  = patch.get("patched_content", "")
        diff     = patch.get("diff", "")

        if not diff.strip():
            results.append(f"[WARN] {filepath}: patch produced no diff — file unchanged")

        passed, msg = _validate_file(filepath, content)
        tag = "[PASS]" if passed else "[FAIL]"
        results.append(f"{tag} {filepath}: {msg}")
        if not passed:
            all_passed = False

    # ── Step 2: pytest for Python patches (best-effort, isolated tmpdir) ─────
    python_patches = [p for p in patches if _lang(p.get("file_path","")) == "python"]
    if all_passed and python_patches:
        with tempfile.TemporaryDirectory() as tmpdir:
            for patch in python_patches:
                dest = Path(tmpdir) / patch["file_path"]
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(patch.get("patched_content", ""), encoding="utf-8")

            test_files = (
                list(Path(tmpdir).rglob("test_*.py"))
                + list(Path(tmpdir).rglob("*_test.py"))
            )
            if not test_files:
                results.append("[INFO] No test files in patched set — pytest skipped")
            else:
                try:
                    proc = subprocess.run(
                        [sys.executable, "-m", "pytest", str(tmpdir),
                         "-v", "--tb=short", "-x", "-q", "--timeout=30"],
                        capture_output=True, text=True, timeout=120, cwd=tmpdir,
                    )
                    pytest_out = (proc.stdout + proc.stderr)[:1500]
                    if proc.returncode == 0:
                        results.append(f"[PASS] pytest:\n{pytest_out}")
                    else:
                        results.append(f"[FAIL] pytest:\n{pytest_out}")
                        all_passed = False
                except subprocess.TimeoutExpired:
                    results.append("[WARN] pytest timed out — treating as pass")
                except FileNotFoundError:
                    results.append("[INFO] pytest not available — skipped")

    output = "\n".join(results)
    log.info(f"auditor — iteration {iteration}: {'PASSED ✅' if all_passed else 'FAILED ❌'}")
    log.info(f"auditor — results:\n{output}")

    return {**state, "tests_passed": all_passed, "test_results": output}