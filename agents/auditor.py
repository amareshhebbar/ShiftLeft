"""
Auditor agent — runs the generated patches through the test suite
in an isolated subprocess sandbox and records the results.
"""

from core.state import ShiftLeftState, TestResult
from tools.sandbox_tools import run_tests_against_patches
from utils.logger import get_logger

log = get_logger(__name__)

MAX_ITERATIONS = 3


def sandbox_node(state: ShiftLeftState) -> ShiftLeftState:
    patches          = state.get("patches") or []
    repo_local_path  = state.get("repo_local_path", "")
    iteration        = state.get("iteration", 1)

    if not patches:
        log.warning("[auditor] no patches to test — marking as failed")
        return {
            **state,
            "test_results": TestResult(passed=False,
                                       output="No patches generated.",
                                       duration=0.0),
            "tests_passed": False,
        }

    if not repo_local_path:
        log.error("[auditor] repo_local_path is empty — cannot run tests")
        return {
            **state,
            "test_results": TestResult(passed=False,
                                       output="repo_local_path missing.",
                                       duration=0.0),
            "tests_passed": False,
        }

    log.info(f"[auditor] running sandbox tests "
             f"(iteration {iteration}/{MAX_ITERATIONS})")

    result = run_tests_against_patches(repo_local_path, patches)
    test_result = TestResult(
        passed=result["passed"],
        output=result["output"],
        duration=result["duration"],
    )

    # Force-pass after max iterations to avoid infinite loop
    force_pass = (not result["passed"]) and (iteration >= MAX_ITERATIONS)
    if force_pass:
        log.warning(f"[auditor] max iterations ({MAX_ITERATIONS}) reached — "
                    f"proceeding to HITL anyway")

    return {
        **state,
        "test_results": test_result,
        "tests_passed": result["passed"] or force_pass,
    }