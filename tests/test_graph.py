
import pytest
from unittest.mock import patch, MagicMock
from core.graph  import shiftleft_app
from core.state  import ShiftLeftState


@pytest.fixture
def minimal_state() -> ShiftLeftState:
    return ShiftLeftState(
        repo_url="https://github.com/test/repo.git",
        run_id="test-run-001",
        trigger_source="test",
        branch_name="shiftleft/run-test-001",
        iteration=0,
        tests_passed=False,
    )


def test_graph_compiles():
    assert shiftleft_app is not None


def test_graph_nodes():
    node_names = set(shiftleft_app.nodes.keys())
    for name in ("cartographer", "triage", "coder", "auditor", "hitl"):
        assert name in node_names, f"Missing node: {name}"