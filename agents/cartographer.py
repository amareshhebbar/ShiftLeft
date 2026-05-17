from __future__ import annotations

import ast
import datetime
import textwrap
from typing import Any, Dict, List

import yaml

from core.state import ShiftLeftState
from tools.gitlab_mcp_tools import (
    get_file_content,
    get_repository_tree,
    list_issues,
)
from utils.config import GITLAB_TARGET_PROJECT
from utils.logger import get_logger

log = get_logger(__name__)

# ── Tunables ───────────────────────────────────────────────────────────────────
MAX_PY_FILES  = 35      
MAX_FILE_CHARS = 12_000 

SKIP_PATTERNS = (
    "test_",
    "/tests/",
    "tests/",
    "/migrations/",
    "migrations/",
    ".shiftleft/",
    "/setup.py",
    "conftest.py",
)


# ── AST helpers ───────────────────────────────────────────────────────────────

def _safe_unparse(node: ast.AST) -> str:
    try:
        return ast.unparse(node) 
    except (AttributeError, Exception):
        return ""


def _ast_summary(source: str) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "functions":   [],
        "classes":     [],
        "imports":     [],
        "loc":         source.count("\n") + 1,
        "parse_error": None,
    }
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        summary["parse_error"] = f"{exc.msg} (line {exc.lineno})"
        return summary
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            child._parent = node  

    collected_imports: List[str] = []
    functions: List[Dict] = []
    classes: List[Dict] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                collected_imports.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                collected_imports.append(node.module.split(".")[0])
                
        elif isinstance(node, ast.ClassDef):
            methods = [
                n.name
                for n in ast.walk(node)
                if isinstance(n, ast.FunctionDef)
                and getattr(n, "_parent", None) is node
            ]
            bases = [_safe_unparse(b) for b in node.bases]
            classes.append({
                "name":     node.name,
                "inherits": [b for b in bases if b],
                "methods":  methods,
                "loc":      (getattr(node, "end_lineno", node.lineno) - node.lineno + 1),
            })

        elif isinstance(node, ast.FunctionDef):
            parent = getattr(node, "_parent", None)
            if not isinstance(parent, ast.Module):
                continue  

            args = []
            for arg in node.args.args:
                ann = f": {_safe_unparse(arg.annotation)}" if arg.annotation else ""
                args.append(f"{arg.arg}{ann}")

            returns = _safe_unparse(node.returns) if node.returns else ""
            docstring = ast.get_docstring(node) or ""

            functions.append({
                "name":      node.name,
                "args":      args,
                "returns":   returns,
                "docstring": textwrap.shorten(docstring, width=160, placeholder="…"),
                "loc":       (getattr(node, "end_lineno", node.lineno) - node.lineno + 1),
                "lineno":    node.lineno,
            })

    summary["functions"] = functions
    summary["classes"]   = classes
    summary["imports"]   = sorted(set(collected_imports))
    return summary


# ── YAML builder ──────────────────────────────────────────────────────────────

def _build_yaml(filepath: str, summary: Dict[str, Any], run_id: str) -> str:
    doc: Dict[str, Any] = {
        "file":          filepath,
        "last_analyzed": run_id,
        "loc":           summary["loc"],
        "imports":       summary["imports"],
    }
    if summary.get("parse_error"):
        doc["parse_error"] = summary["parse_error"]

    doc["functions"] = [
        {
            "name":      fn["name"],
            "args":      fn["args"],
            "returns":   fn["returns"] or "None",
            "docstring": fn["docstring"],
            "loc":       fn["loc"],
        }
        for fn in summary["functions"]
    ]
    doc["classes"] = [
        {
            "name":     cls["name"],
            "inherits": cls["inherits"],
            "methods":  cls["methods"],
            "loc":      cls["loc"],
        }
        for cls in summary["classes"]
    ]
    return yaml.dump(doc, default_flow_style=False, allow_unicode=True, sort_keys=False)


# ── Agent entry point ──────────────────────────────────────────────────────────

def cartographer(state: ShiftLeftState) -> ShiftLeftState:
    run_id  = datetime.datetime.utcnow().strftime("%Y-%m-%d_%H%M%S")
    project = GITLAB_TARGET_PROJECT

    log.info(f"cartographer — run_id={run_id}  project={project}")
    log.info("cartographer — fetching repository tree via GitLab REST API")
    try:
        tree = get_repository_tree(project=project, recursive=True)
    except Exception as exc:
        log.error(f"cartographer — tree fetch failed: {exc}")
        raise

    py_files: List[str] = []
    for item in tree:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "blob":
            continue
        path = item.get("path", "")
        if not path.endswith(".py"):
            continue
        if any(skip in path for skip in SKIP_PATTERNS):
            continue
        py_files.append(path)

    py_files = py_files[:MAX_PY_FILES]
    log.info(f"cartographer — {len(py_files)} Python files selected (tree had {len(tree)} items)")
    file_map:  Dict[str, Any] = {}
    yaml_map:  Dict[str, str] = {}
    errors:    List[str]      = []

    for filepath in py_files:
        try:
            content = get_file_content(filepath, project=project)
            if not content.strip():
                log.warning(f"cartographer — {filepath} is empty, skipping")
                continue
            if len(content) > MAX_FILE_CHARS:
                content = content[:MAX_FILE_CHARS] + "\n# [ShiftLeft: file truncated]\n"

            summary = _ast_summary(content)
            summary["raw_content"] = content 
            file_map[filepath] = summary

            yaml_content = _build_yaml(filepath, summary, run_id)
            yaml_key = f".shiftleft/map/{filepath.removesuffix('.py')}.yaml"
            yaml_map[yaml_key] = yaml_content

            log.info(
                f"cartographer — {filepath}  "
                f"({summary['loc']} loc, "
                f"{len(summary['functions'])} funcs, "
                f"{len(summary['classes'])} classes)"
            )
        except Exception as exc:
            log.warning(f"cartographer — skipping {filepath}: {exc}")
            errors.append(f"{filepath}: {exc}")
    config_doc = {
        "version":          "1.0",
        "project":          project,
        "schedule":         "0 2 * * *",
        "base_branch":      "main",
        "ignore":           list(SKIP_PATTERNS),
        "max_files_per_run": MAX_PY_FILES,
    }
    yaml_map[".shiftleft/config.yaml"] = yaml.dump(
        config_doc, default_flow_style=False, allow_unicode=True
    )

    manifest_doc = {
        "run_id":          run_id,
        "files_analyzed":  len(file_map),
        "files_skipped":   len(errors),
        "generated_at":    run_id,
        "python_files":    py_files,
        "skip_errors":     errors[:10],
    }
    yaml_map[".shiftleft/manifest.yaml"] = yaml.dump(
        manifest_doc, default_flow_style=False, allow_unicode=True
    )

    log.info(f"cartographer — {len(yaml_map)} YAML manifests built")
    log.info("cartographer — fetching open issues via GitLab MCP")
    try:
        open_issues = list_issues(project=project, state="opened", per_page=20)
        if not isinstance(open_issues, list):
            open_issues = []
        log.info(f"cartographer — {len(open_issues)} open issues loaded")
        for issue in open_issues[:5]:
            log.info(f"  #{issue.get('iid','?')} {issue.get('title','')}")
    except Exception as exc:
        log.warning(f"cartographer — could not fetch issues: {exc}")
        open_issues = []

    return {
        **state,
        "run_id":             run_id,
        "gitlab_project_id":  project,
        "branch_name":        f"shiftleft/run-{run_id}",
        "file_map":           file_map,
        "yaml_map":           yaml_map,
        "open_issues":        open_issues,
        "repo_local_path":    "", 
    }