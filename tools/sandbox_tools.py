"""
Runs pytest against a list of patches in an isolated temporary directory.
Applies patches to a copy of the repo, then executes the test suite.
"""

import os
import shutil
import subprocess
import tempfile
from typing import List, Dict, Any

from utils.logger import get_logger

log = get_logger(__name__)


def run_tests_against_patches(
    repo_local_path: str,
    patches: List[Dict],
    timeout: int = 120,
) -> Dict[str, Any]:
    """
    Apply patches to a temp copy of the repo, run pytest, return results.

    patches: list of {filename: str, content: str}
    Returns: {passed: bool, output: str, duration: float}
    """
    import time

    with tempfile.TemporaryDirectory() as sandbox:
        # copy the entire repo into the sandbox
        sandbox_repo = os.path.join(sandbox, "repo")
        shutil.copytree(repo_local_path, sandbox_repo,
                        ignore=shutil.ignore_patterns(".git"))

        # apply patches
        for patch in patches:
            target = os.path.join(sandbox_repo, patch["filename"])
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w") as f:
                f.write(patch["content"])

        log.info(f"[sandbox] applied {len(patches)} patch(es), running tests…")
        t0 = time.monotonic()

        result = subprocess.run(
            ["python", "-m", "pytest", "--tb=short", "-q", "--no-header"],
            cwd=sandbox_repo,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        duration = round(time.monotonic() - t0, 2)
        output   = (result.stdout + result.stderr).strip()
        passed   = result.returncode == 0

        log.info(f"[sandbox] tests {'PASSED' if passed else 'FAILED'} "
                 f"in {duration}s")
        return {"passed": passed, "output": output, "duration": duration}