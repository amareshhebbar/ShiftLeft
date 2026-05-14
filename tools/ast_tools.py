"""
Python AST analysis.
Extracts function signatures, class definitions, and module docstrings
from .py source files. Returns structured dicts ready for YAML serialisation.
"""

import ast
import os
from typing import Dict, List, Any


def _annotation(node) -> str:
    """Convert an AST annotation node to a readable string."""
    if node is None:
        return "Any"
    try:
        return ast.unparse(node)
    except Exception:
        return "Any"


def _docstring_first_line(node) -> str:
    doc = ast.get_docstring(node)
    if not doc:
        return "(no docstring)"
    return doc.split("\n")[0].strip()


def extract_functions(source: str) -> List[Dict]:
    """
    Returns a list of function descriptors from Python source code.
    Skips private helpers (single leading underscore) but keeps dunders.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    results = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        name = node.name
        if name.startswith("_") and not name.startswith("__"):
            continue

        args = []
        for arg in node.args.args:
            ann = _annotation(arg.annotation)
            label = f"{arg.arg}: {ann}" if ann != "Any" else arg.arg
            args.append(label)

        results.append({
            "name":    name,
            "async":   isinstance(node, ast.AsyncFunctionDef),
            "takes":   args,
            "returns": _annotation(node.returns),
            "does":    _docstring_first_line(node),
            "line":    node.lineno,
        })
    return results


def extract_classes(source: str) -> List[Dict]:
    """Returns a list of class descriptors from Python source code."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    results = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        bases = [ast.unparse(b) for b in node.bases] if node.bases else []
        methods = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                m_args = [a.arg for a in item.args.args if a.arg != "self"]
                methods.append({
                    "name":    item.name,
                    "takes":   m_args,
                    "returns": _annotation(item.returns),
                    "does":    _docstring_first_line(item),
                })
        results.append({
            "name":     node.name,
            "inherits": bases[0] if bases else None,
            "does":     _docstring_first_line(node),
            "methods":  methods,
        })
    return results


def analyse_file(abs_path: str) -> Dict[str, Any]:
    """
    Top-level function: read a .py file and return a complete meta dict.
    Returns {"purpose", "functions", "classes", "lines"}.
    """
    try:
        with open(abs_path, "r", errors="replace") as f:
            source = f.read()
    except OSError:
        return {"purpose": "unreadable", "functions": [], "classes": [], "lines": 0}

    purpose = "(no module docstring)"
    try:
        tree = ast.parse(source)
        mod_doc = ast.get_docstring(tree)
        if mod_doc:
            purpose = mod_doc.split("\n")[0].strip()
    except SyntaxError:
        pass

    return {
        "purpose":   purpose,
        "functions": extract_functions(source),
        "classes":   extract_classes(source),
        "lines":     len(source.splitlines()),
    }


IGNORE_DIRS = {
    ".git", "__pycache__", ".venv", "venv", "node_modules",
    ".shiftleft", "dist", "build", ".eggs", ".tox",
}


def walk_repo(repo_root: str) -> Dict[str, Any]:
    """
    Walk an entire repository and return {rel_path: analyse_file_result}
    for every .py file found. Prunes common non-source directories.
    """
    result: Dict[str, Any] = {}
    for dirpath, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        for fname in filenames:
            if not fname.endswith(".py"):
                continue
            abs_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(abs_path, repo_root)
            result[rel_path] = analyse_file(abs_path)
    return result