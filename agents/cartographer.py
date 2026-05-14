"""
Cartographer agent — the first node in the ShiftLeft pipeline.

Responsibilities:
  1. Clone (or pull) the target repository locally.
  2. Run AST analysis on every Python file.
  3. Write the .shiftleft/ YAML tree into the local clone.
  4. Capture all YAML content in state for the HITL agent to commit.
  5. Set branch_name and run_id for the rest of the pipeline.
"""

import os
import subprocess
import tempfile
from datetime import datetime, timezone

from core.state import ShiftLeftState
from tools.ast_tools import walk_repo
from tools.yaml_tools import (
    write_config,
    write_manifest,
    write_file_yaml,
    collect_yaml_files,
)
from utils.config import DEFAULT_BASE_BRANCH
from utils.logger import get_logger

log = get_logger(__name__)


def _run(cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kwargs)


def _clone_repo(repo_url: str, dest: str) -> None:
    """Shallow clone for speed; fall back to full clone on error."""
    try:
        _run(["git", "clone", "--depth", "1", "--quiet", repo_url, dest])
    except subprocess.CalledProcessError:
        log.warning("[cartographer] shallow clone failed, trying full clone")
        _run(["git", "clone", "--quiet", repo_url, dest])


def _folder_descriptions(file_map: dict) -> dict:
    """Produce a {folder: description} dict from the file map."""
    folders: dict = {}
    for rel_path in file_map:
        parts   = rel_path.replace("\\", "/").split("/")
        top_dir = parts[0] if len(parts) > 1 else "."
        folders.setdefault(top_dir, []).append(rel_path)
    return {
        folder: f"{len(files)} Python file(s) — auto-mapped by ShiftLeft"
        for folder, files in sorted(folders.items())
    }


def cartographer_node(state: ShiftLeftState) -> ShiftLeftState:
    repo_url = state["repo_url"]
    run_id   = state.get("run_id") or \
               datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    branch   = f"shiftleft/run-{run_id}"

    log.info(f"[cartographer] run_id={run_id}, cloning {repo_url}")

    # We use a persistent temp dir so auditor can reference it later.
    # The caller (main.py / webhook) is responsible for cleanup.
    tmp = tempfile.mkdtemp(prefix="shiftleft_")
    _clone_repo(repo_url, tmp)

    # write .shiftleft/config.yaml (only on first run; no-op after that)
    write_config(tmp, {"base_branch": DEFAULT_BASE_BRANCH})

    # walk the entire repo with AST
    file_map = walk_repo(tmp)
    log.info(f"[cartographer] mapped {len(file_map)} Python files")

    # write per-file YAMLs
    for rel_path, meta in file_map.items():
        write_file_yaml(tmp, rel_path, meta)

    # write folder manifest
    write_manifest(tmp, _folder_descriptions(file_map))

    # read all .shiftleft/ files back into memory for HITL to commit
    yaml_map = collect_yaml_files(tmp)
    log.info(f"[cartographer] generated {len(yaml_map)} YAML files")

    return {
        **state,
        "run_id":          run_id,
        "branch_name":     branch,
        "file_map":        file_map,
        "yaml_map":        yaml_map,
        "repo_local_path": tmp,
        "iteration":       0,
    }