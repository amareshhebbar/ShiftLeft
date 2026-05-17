from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import threading
import time
from typing import Any, Dict, List, Optional

import httpx

from utils.config import GITLAB_TOKEN, GITLAB_TARGET_PROJECT, GITLAB_URL
from utils.logger import get_logger

log = get_logger(__name__)

# ── Branch cache ───────────────────────────────────────────────────────────────
_branch_cache: Dict[str, str] = {}

def _default_branch(project: str) -> str:
    if project in _branch_cache:
        return _branch_cache[project]
    try:
        enc = project.replace("/", "%2F")
        resp = httpx.get(
            f"{GITLAB_URL}/api/v4/projects/{enc}",
            headers={"PRIVATE-TOKEN": GITLAB_TOKEN},
            timeout=15,
        )
        resp.raise_for_status()
        branch = resp.json().get("default_branch", "main")
    except Exception as e:
        log.warning(f"Could not detect default branch for {project}: {e} — assuming 'main'")
        branch = "main"
    _branch_cache[project] = branch
    log.info(f"Default branch for {project}: {branch}")
    return branch


# ── Subprocess MCP client ──────────────────────────────────────────────────────

class _MCPClient:
    def __init__(self) -> None:
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._req_id = 0

    def _start(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return

        npx = shutil.which("npx")
        if not npx:
            raise RuntimeError(
                "npx not found. Install Node.js then: npm install -g @modelcontextprotocol/server-gitlab"
            )

        env = {
            **os.environ,
            "GITLAB_PERSONAL_ACCESS_TOKEN": GITLAB_TOKEN,
            "GITLAB_API_URL": f"{GITLAB_URL}/api/v4",
        }

        log.info("MCP — starting @modelcontextprotocol/server-gitlab")
        self._proc = subprocess.Popen(
            [npx, "-y", "@modelcontextprotocol/server-gitlab"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
            bufsize=1,
        )
        time.sleep(1.0)

        if self._proc.poll() is not None:
            stderr = self._proc.stderr.read()
            raise RuntimeError(f"MCP server died at startup:\n{stderr[:600]}")

        self._req_id += 1
        self._write({
            "jsonrpc": "2.0", "id": self._req_id, "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "clientInfo": {"name": "shiftleft", "version": "1.0"},
            },
        })
        resp = self._read_until_id(self._req_id)
        if "error" in resp:
            raise RuntimeError(f"MCP init error: {resp['error']}")

        self._write({"jsonrpc": "2.0", "method": "notifications/initialized"})
        log.info("MCP — server initialized")

    def _write(self, obj: dict) -> None:
        self._proc.stdin.write(json.dumps(obj) + "\n")
        self._proc.stdin.flush()

    def _read_until_id(self, target_id: int, timeout: float = 30.0) -> dict:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._proc.poll() is not None:
                stderr = ""
                try: stderr = self._proc.stderr.read(500)
                except: pass
                raise RuntimeError(f"MCP server died. stderr: {stderr}")
            line = self._proc.stdout.readline()
            if not line:
                time.sleep(0.05)
                continue
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("id") == target_id:
                return msg
        raise TimeoutError(f"MCP timed out waiting for response to request {target_id}")

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        with self._lock:
            self._start()
            self._req_id += 1
            req_id = self._req_id
            self._write({
                "jsonrpc": "2.0", "id": req_id,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            })
            resp = self._read_until_id(req_id)

        if "error" in resp:
            raise RuntimeError(
                f"MCP tool '{name}' error [{resp['error'].get('code','?')}]: "
                f"{resp['error'].get('message', str(resp['error']))}"
            )
        result = resp.get("result", {})
        if result.get("isError"):
            text = "".join(c.get("text","") for c in result.get("content",[]))
            raise RuntimeError(f"MCP tool '{name}' isError=true: {text[:300]}")

        content = result.get("content", [])
        if not content:
            return result
        text = content[0].get("text", "")
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return text

    def list_tools(self) -> List[str]:
        with self._lock:
            self._start()
            self._req_id += 1
            req_id = self._req_id
            self._write({"jsonrpc": "2.0", "id": req_id, "method": "tools/list", "params": {}})
            resp = self._read_until_id(req_id)
        if "error" in resp:
            raise RuntimeError(f"MCP tools/list error: {resp['error']}")
        return [t["name"] for t in resp.get("result", {}).get("tools", [])]

    def close(self) -> None:
        if self._proc:
            try: self._proc.terminate(); self._proc.wait(timeout=5)
            except: pass
            self._proc = None


_client = _MCPClient()
import atexit; atexit.register(_client.close)


# ── Public API — reads (REST) ──────────────────────────────────────────────────

def list_available_tools() -> List[str]:
    return _client.list_tools()


def get_repository_tree(
    project: str = None, path: str = "",
    recursive: bool = True, ref: str = None,
) -> List[Dict]:
    project = project or GITLAB_TARGET_PROJECT
    ref = ref or _default_branch(project)
    enc = project.replace("/", "%2F")
    url = f"{GITLAB_URL}/api/v4/projects/{enc}/repository/tree"
    headers = {"PRIVATE-TOKEN": GITLAB_TOKEN}
    params: Dict[str, Any] = {"recursive": str(recursive).lower(), "per_page": 100, "ref": ref}
    if path:
        params["path"] = path

    all_items: List[Dict] = []
    page = 1
    while True:
        params["page"] = page
        resp = httpx.get(url, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        items = resp.json()
        if not items:
            break
        all_items.extend(items)
        if len(items) < 100:
            break
        page += 1
    return all_items


def get_file_content(file_path: str, project: str = None, ref: str = None) -> str:
    project = project or GITLAB_TARGET_PROJECT
    ref = ref or _default_branch(project)
    try:
        result = _client.call_tool("get_file_contents", {
            "project_id": project,
            "file_path":  file_path,
            "ref":        ref,
        })
        if isinstance(result, dict) and "content" in result:
            try:
                return base64.b64decode(result["content"]).decode("utf-8", errors="replace")
            except Exception:
                return str(result["content"])
        if isinstance(result, str):
            return result
        return str(result)
    except RuntimeError as e:
        if "not found" not in str(e).lower() and "404" not in str(e):
            raise
        log.warning(f"MCP get_file_contents 404 for {file_path}, falling back to REST")
    enc_proj = project.replace("/", "%2F")
    enc_file = file_path.replace("/", "%2F")
    resp = httpx.get(
        f"{GITLAB_URL}/api/v4/projects/{enc_proj}/repository/files/{enc_file}",
        params={"ref": ref},
        headers={"PRIVATE-TOKEN": GITLAB_TOKEN},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return base64.b64decode(data["content"]).decode("utf-8", errors="replace")


def list_issues(
    project: str = None, state: str = "opened", per_page: int = 20,
) -> List[Dict]:
    project = project or GITLAB_TARGET_PROJECT
    enc = project.replace("/", "%2F")
    resp = httpx.get(
        f"{GITLAB_URL}/api/v4/projects/{enc}/issues",
        params={"state": state, "per_page": per_page, "order_by": "updated_at"},
        headers={"PRIVATE-TOKEN": GITLAB_TOKEN},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


# ── Public API — writes (MCP) ──────────────────────────────────────────────────

def create_branch(branch: str, ref: str = None, project: str = None) -> Dict:
    project = project or GITLAB_TARGET_PROJECT
    ref = ref or _default_branch(project)
    return _client.call_tool("create_branch", {
        "project_id": project, "branch": branch, "ref": ref,
    })


def push_files(
    branch: str, files: List[Dict[str, str]], message: str, project: str = None,
) -> Dict:
    project = project or GITLAB_TARGET_PROJECT
    return _client.call_tool("push_files", {
        "project_id": project, "branch": branch,
        "commit_message": message, "files": files,
    })


def create_merge_request(
    branch: str, title: str, description: str,
    project: str = None, target: str = None,
) -> Dict:
    project = project or GITLAB_TARGET_PROJECT
    target = target or _default_branch(project)
    return _client.call_tool("create_merge_request", {
        "project_id": project, "source_branch": branch,
        "target_branch": target, "title": title, "description": description,
    })


def create_issue(
    title: str, description: str,
    labels: List[str] = None, project: str = None,
) -> Dict:
    project = project or GITLAB_TARGET_PROJECT
    return _client.call_tool("create_issue", {
        "project_id": project, "title": title,
        "description": description,
        # GitLab API expects labels as comma-separated string, not array
        "labels": ",".join(labels) if labels else "shiftleft,automated",
    })


def create_or_update_file(
    file_path: str, content: str, commit_message: str,
    branch: str, project: str = None, encoding: str = "text",
) -> Dict:
    project = project or GITLAB_TARGET_PROJECT
    return _client.call_tool("create_or_update_file", {
        "project_id":     project,
        "file_path":      file_path,
        "content":        content,
        "commit_message": commit_message,
        "branch":         branch,
        "encoding":       encoding,
    })