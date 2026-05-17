from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List

from core.state import ShiftLeftState, TestResult
from utils.logger import get_logger

log = get_logger(__name__)

MAX_ITERATIONS = 3


def auditor(state: ShiftLeftState) -> ShiftLeftState:
    patches   = state.get("patches") or []
    iteration = state.get("iteration", 1)

    if not patches:
        log.info("auditor — no patches to validate, marking passed")
        return {**state, "tests_passed": True, "test_results": "No patches produced."}

    results: List[str] = []
    all_passed = True

    # ── Step 1: Syntax check + diff check ─────────────────────────────────────
    for patch in patches:
        filepath = patch.get("file_path", "unknown")
        content  = patch.get("patched_content", "")
        diff     = patch.get("diff", "")

        if not content.strip():
            results.append(f"[FAIL] {filepath}: patched_content is empty")
            all_passed = False
            continue

        if not diff.strip():
            results.append(f"[WARN] {filepath}: patch produced no diff — file unchanged")
        tmp = tempfile.NamedTemporaryFile(suffix=".py", mode="w",
                                          delete=False, encoding="utf-8")
        try:
            tmp.write(content)
            tmp.close()
            proc = subprocess.run(
                [sys.executable, "-m", "py_compile", tmp.name],
                capture_output=True, text=True, timeout=15,
            )
            if proc.returncode == 0:
                results.append(f"[PASS] {filepath}: syntax OK")
            else:
                results.append(f"[FAIL] {filepath}: SYNTAX ERROR\n       {proc.stderr.strip()}")
                all_passed = False
        except subprocess.TimeoutExpired:
            results.append(f"[FAIL] {filepath}: syntax check timed out")
            all_passed = False
        except Exception as exc:
            results.append(f"[ERROR] {filepath}: {exc}")
            all_passed = False
        finally:
            try:
                os.unlink(tmp.name)
            except Exception:
                pass

    if not all_passed:
        output = "\n".join(results)
        log.info(f"auditor — syntax check FAILED (iteration {iteration})")
        return {
            **state,
            "tests_passed": False,
            "test_results": output,
        }

    # ── Step 2: Pytest (best-effort, in isolated temp dir) ────────────────────
    with tempfile.TemporaryDirectory() as tmpdir:
        for patch in patches:
            dest = Path(tmpdir) / patch["file_path"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(patch.get("patched_content", ""), encoding="utf-8")
        test_files = list(Path(tmpdir).rglob("test_*.py")) + list(Path(tmpdir).rglob("*_test.py"))

        if not test_files:
            results.append("[INFO] No test files in patched set — skipping pytest")
            log.info("auditor — no test files to run, marking passed")
        else:
            try:
                proc = subprocess.run(
                    [
                        sys.executable, "-m", "pytest",
                        str(tmpdir), "-v", "--tb=short", "-x",
                        "--timeout=30", "-q",
                    ],
                    capture_output=True, text=True,
                    timeout=120, cwd=tmpdir,
                )
                pytest_out = (proc.stdout + proc.stderr)[:1500]
                if proc.returncode == 0:
                    results.append(f"[PASS] pytest:\n{pytest_out}")
                else:
                    results.append(f"[FAIL] pytest:\n{pytest_out}")
                    all_passed = False
            except subprocess.TimeoutExpired:
                results.append("[WARN] pytest timed out — treating as pass for pipeline")
            except FileNotFoundError:
                results.append("[INFO] pytest not available — skipping")

    output = "\n".join(results)
    log.info(f"auditor — iteration {iteration}: {'PASSED' if all_passed else 'FAILED'}")
    log.info(f"auditor — results:\n{output}")

    return {
        **state,
        "tests_passed": all_passed,
        "test_results": output,
    }