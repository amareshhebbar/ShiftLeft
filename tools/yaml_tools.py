"""
Writes the .shiftleft/ YAML tree into a cloned repository directory.
All functions are idempotent — safe to call on every run.
"""

import os
import yaml
from datetime import datetime, timezone
from typing import Dict, Any


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


def write_config(repo_root: str, overrides: Dict = None) -> str:
    """
    Write .shiftleft/config.yaml on first run.
    If the file already exists it is NOT overwritten — the user's settings are preserved.
    """
    path = os.path.join(repo_root, ".shiftleft", "config.yaml")
    if os.path.exists(path):
        return path
    defaults: Dict[str, Any] = {
        "version": 1,
        "ignore": ["node_modules", ".venv", "venv", "__pycache__", ".git", "dist"],
        "schedule": "0 2 * * *",
        "auto_pr": True,
        "base_branch": "main",
        "max_files_per_run": 5,
        "severity_threshold": "medium",
        "notify_slack": False,
    }
    if overrides:
        defaults.update(overrides)
    _write(path, defaults)
    return path


def write_manifest(repo_root: str, folder_descriptions: Dict[str, str]) -> str:
    """Write .shiftleft/manifest.yaml — folder-level purpose map."""
    path = os.path.join(repo_root, ".shiftleft", "manifest.yaml")
    _write(path, {
        "generated_by": "shiftleft-cartographer",
        "generated_at": _utcnow(),
        "folders":       folder_descriptions,
    })
    return path


def write_file_yaml(repo_root: str, rel_path: str, file_meta: Dict) -> str:
    """
    Write .shiftleft/map/<rel_path>.yaml for one source file.

    file_meta comes directly from ast_tools.analyse_file():
    {
        "purpose":   "short description from module docstring",
        "functions": [{name, takes, returns, does, line}, ...],
        "classes":   [{name, inherits, does, methods}, ...],
        "lines":     int
    }
    """
    # normalise path separators for the YAML key name
    safe_rel = rel_path.replace(os.sep, "/")
    yaml_path = os.path.join(repo_root, ".shiftleft", "map",
                             safe_rel + ".yaml")
    _write(yaml_path, {
        "path":         safe_rel,
        "generated_at": _utcnow(),
        **file_meta,
    })
    return os.path.relpath(yaml_path, repo_root)


def write_audit_result(repo_root: str, run_id: str, audit: Dict) -> str:
    """Write .shiftleft/audits/<run_id>.yaml — one record per pipeline run."""
    path = os.path.join(repo_root, ".shiftleft", "audits", f"{run_id}.yaml")
    _write(path, {
        "run_id":    run_id,
        "timestamp": _utcnow(),
        **audit,
    })
    return path


def collect_yaml_files(repo_root: str) -> Dict[str, str]:
    """
    Read all generated .shiftleft/ YAML files and return them as
    {repo-relative-path: file-content-string} so HITL can commit them
    to GitHub without re-reading from disk.
    """
    shiftleft_dir = os.path.join(repo_root, ".shiftleft")
    result: Dict[str, str] = {}
    if not os.path.exists(shiftleft_dir):
        return result
    for dirpath, _, fnames in os.walk(shiftleft_dir):
        for fname in fnames:
            abs_f = os.path.join(dirpath, fname)
            rel_f = os.path.relpath(abs_f, repo_root).replace(os.sep, "/")
            with open(abs_f, "r", errors="replace") as f:
                result[rel_f] = f.read()
    return result