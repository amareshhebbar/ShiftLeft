# ShiftLeft — Architecture Deep Dive

> Every design decision in ShiftLeft was made deliberately. This document explains not just *what* was built, but *why* each technical choice was made over the alternatives.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Why LangGraph over Alternatives](#2-why-langgraph-over-alternatives)
3. [Why Vertex AI over AI Studio](#3-why-vertex-ai-over-ai-studio)
4. [The LLM Abstraction Layer](#4-the-llm-abstraction-layer)
5. [Why GitLab MCP + REST Hybrid](#5-why-gitlab-mcp--rest-hybrid)
6. [Agent Design: Cartographer](#6-agent-design-cartographer)
7. [Agent Design: Triage](#7-agent-design-triage)
8. [Agent Design: Coder](#8-agent-design-coder)
9. [Agent Design: Auditor](#9-agent-design-auditor)
10. [Agent Design: HITL](#10-agent-design-hitl)
11. [The State Schema](#11-the-state-schema)
12. [The Retry Loop](#12-the-retry-loop)
13. [The .shiftleft/ Knowledge Base](#13-the-shiftleft-knowledge-base)
14. [Arize Phoenix Observability](#14-arize-phoenix-observability)
15. [Cloud Run Deployment Model](#15-cloud-run-deployment-model)
16. [What Was Deliberately Not Built](#16-what-was-deliberately-not-built)

---

## 1. System Overview

ShiftLeft is a **closed-loop autonomous software engineering system**. The full data flow from trigger to MR:

```
GitLab issue labeled "shiftleft"
          │
          ▼ (HTTP POST from GitLab webhook)
Cloud Run: cloud/web_hook.py
          │  verifies X-Gitlab-Token
          │  extracts project + issue IID
          │  returns HTTP 200 immediately
          │
          ▼ (background task — non-blocking)
LangGraph: core/graph.py
          │
          ├─▶ Cartographer ──────────────────────────────────────────────────┐
          │     GitLab REST: GET /repository/tree (paginated, recursive)     │
          │     GitLab MCP:  get_file_contents (one call per source file)    │
          │     Python ast:  parse every .py file                            │
          │     GitLab REST: GET /issues (open, ordered by updated_at)       │
          │     Output:      file_map{} + open_issues[] + yaml_map{}         │
          │                                                                   │
          ├─▶ Triage ────────────────────────────────────────────────────────┤
          │     Vertex AI:   vertexai.GenerativeModel.generate_content()     │
          │     Prompt:      entire file_map + issue list (up to 1M tokens)  │
          │     Temp:        0.1 (near-deterministic — we want one answer)   │
          │     Output:      target_files[] + severity + issue_summary       │
          │                                                                   │
          ├─▶ Coder ─────────────────────────────────────────────────────────┤
          │     Vertex AI:   vertexai.GenerativeModel.generate_content()     │
          │     Prompt:      full source file + bug summary + (retry: diff)  │
          │     Temp:        0.15 (slight creativity for code generation)    │
          │     Output:      patches[]{file_path, patched_content, diff}     │
          │                                                                   │
          ├─▶ Auditor ───────────────────────────────────────────────────────┤
          │     Python:      py_compile in temp dir                          │
          │     JavaScript:  node --check in temp dir                        │
          │     TypeScript:  tsc --noEmit in temp dir (if tsc installed)     │
          │     Go:          go vet in temp dir (if go installed)            │
          │     Python:      pytest (if test files exist in patch set)       │
          │     Output:      tests_passed bool + test_results string         │
          │                                                                   │
          │     ┌── FAIL + iteration < 3 ──▶ back to Coder with diff context┤
          │     └── PASS or iteration >= 3 ──▶ HITL                         │
          │                                                                   │
          └─▶ HITL ──────────────────────────────────────────────────────────┘
                GitLab MCP:  create_branch (MCP works reliably here)
                REST API:    POST /repository/commits (source files)
                REST API:    POST /repository/commits (YAML manifests)
                REST API:    POST /merge_requests
                Output:      pr_url + pr_number
```

**Total: 2 Vertex AI calls. 0 external databases. 0 vector stores. ~57 seconds average.**

---

## 2. Why LangGraph over Alternatives

The orchestration choice was between: **LangGraph**, CrewAI, AutoGen, plain Python, and Prefect/Temporal.

### Why not CrewAI?

CrewAI is agent-centric: you define agents and tasks, and CrewAI decides execution order. This is fine for loosely-coupled workflows, but ShiftLeft requires a **specific, deterministic sequence with a conditional retry edge**. CrewAI's abstraction layer would obscure the retry logic and make debugging harder.

More importantly: CrewAI's state management is implicit. In ShiftLeft, the entire pipeline shares a single typed `ShiftLeftState` dict — every agent reads from it and writes to it. This makes the data flow explicit and auditable. With CrewAI, you'd be fighting the framework to achieve this.

### Why not AutoGen?

AutoGen's multi-agent conversation model is designed for agents that *talk to each other* in natural language. ShiftLeft agents don't converse — they transform structured data. The Cartographer doesn't negotiate with the Triage agent about which files to include. It produces a file map and hands it off. AutoGen's conversation overhead would add latency and unpredictability with no benefit.

### Why not plain Python?

A plain Python pipeline (`cartographer() → triage() → coder() → auditor() → hitl()`) would work, but loses two things:
1. **The conditional retry edge** becomes imperative `while` loop logic tangled with the main flow
2. **State transitions are not tracked** — LangGraph records every node transition, which Arize Phoenix can instrument as spans

### Why LangGraph?

LangGraph models the pipeline as a **directed graph with typed state**. The retry loop becomes a declarative routing function:

```python
def route_after_audit(state: ShiftLeftState) -> str:
    if state["tests_passed"]:          return "hitl"
    if state["iteration"] >= MAX_ITER: return "hitl"
    return "coder"
```

This is clean, testable, and makes the control flow visible in the graph definition (`core/graph.py`). LangGraph also integrates natively with LangChain's OpenInference instrumentation, which is what makes Arize tracing possible with a single import.

**The retry edge is the core innovation.** Most agent systems are DAGs (directed acyclic graphs). LangGraph allows cycles — which is exactly what "try again with the error as context" requires.

---

## 3. Why Vertex AI over AI Studio

This is the most important architectural decision for the hackathon and for production use.

### What is the difference?

| | AI Studio (google-generativeai) | Vertex AI (google-cloud-aiplatform) |
|---|---|---|
| Authentication | API key in env var | Application Default Credentials / Service Account |
| Deployment model | Consumer product | Enterprise Google Cloud service |
| Pricing | Free tier, then per-token | Per-token, no free tier |
| IAM | None | Full GCP IAM roles |
| Audit logging | None | Cloud Audit Logs |
| VPC / private networking | Not available | Available |
| Hackathon requirement | ❌ Does not satisfy "Google Cloud AI" | ✅ Satisfies "Google Cloud AI tools" |

### Why this matters for the hackathon

The rapid-agent.devpost.com rules state: "use Google Cloud artificial intelligence tools." AI Studio is a consumer product — the same one you access at aistudio.google.com. Vertex AI is the enterprise Google Cloud service. The example given in the rules is "Gemini models on Agent Platform" — that is Vertex AI.

Using AI Studio would likely result in the project failing the Google Cloud integration requirement at Stage 1 review.

### How ShiftLeft implements Vertex AI

```python
# utils/llm.py

import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig

vertexai.init(project=GCP_PROJECT_ID, location=GCP_REGION)

def generate(prompt: str, temperature: float = 0.1, max_tokens: int = 16384) -> str:
    model = GenerativeModel(GEMINI_MODEL)
    response = model.generate_content(
        prompt,
        generation_config=GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        ),
    )
    return response.text
```

No API key. No secret. Authentication is handled entirely by the GCP credential chain — `google.auth.default()` finds Application Default Credentials in development and the attached service account in Cloud Run.

### The fallback design

When `GCP_PROJECT_ID` is not set, `utils/llm.py` automatically falls back to AI Studio via `google-generativeai`. This enables local development without a GCP project. The fallback is logged clearly:

```
[WARNING] LLM backend: AI Studio (fallback). Set GCP_PROJECT_ID to use Vertex AI.
```

Agents never import the LLM SDK directly. They call `from utils.llm import generate`. Swapping backends requires changing one file.

---

## 4. The LLM Abstraction Layer

`utils/llm.py` is the single most important architectural decision after LangGraph.

### The problem it solves

Without an abstraction layer, each agent would import `google.generativeai` or `vertexai` directly:

```python
# BAD — what we had before
import google.generativeai as genai
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(GEMINI_MODEL)
resp = model.generate_content(prompt, ...)
```

This means:
1. Switching from AI Studio to Vertex AI requires editing 2+ agent files
2. Testing agents requires mocking a specific SDK
3. Adding token counting or tracing requires modifying every agent
4. The fallback logic is duplicated across files

### The abstraction

```python
# utils/llm.py
def generate(prompt, temperature=0.1, max_tokens=16384, model_override=None) -> str:
    """Single entry point for all LLM calls in the pipeline."""
```

Every agent calls this one function. The backend (Vertex AI or AI Studio) is selected once at module load time based on the presence of `GCP_PROJECT_ID`. Arize instrumentation hooks into this function automatically.

### backend_info()

```python
def backend_info() -> dict:
    """Returns the active backend config for MR descriptions and UI display."""
    if USE_VERTEX:
        return {"backend": "Vertex AI", "project": GCP_PROJECT_ID, ...}
    return {"backend": "AI Studio (fallback)", ...}
```

This is called by the HITL agent to include the LLM backend information in every MR description — judges can see exactly which Google Cloud service generated the fix.

---

## 5. Why GitLab MCP + REST Hybrid

ShiftLeft uses **both** the GitLab MCP server and the GitLab REST API. This is intentional, not a limitation.

### What GitLab MCP provides

The `@modelcontextprotocol/server-gitlab` npm package implements the Model Context Protocol — a standardized JSON-RPC protocol for AI tools to interact with external services. MCP is the hackathon's partner integration requirement.

MCP tools used by ShiftLeft:
- `get_file_contents` — reads source files (used by Cartographer)
- `create_branch` — creates the fix branch (used by HITL)

These two operations work reliably through the MCP subprocess client (`tools/gitlab_mcp_tools.py`).

### Why REST for commits and MR creation

The `@modelcontextprotocol/server-gitlab` package has a JavaScript bug in its `push_files` implementation — it calls `.map()` on a value that is sometimes `undefined`, causing a crash on the Node.js side. This bug is in the npm package's source, not in ShiftLeft.

Rather than working around an upstream bug with fragile string manipulation, ShiftLeft uses the GitLab Commits REST API directly for:
- Pushing source file patches
- Committing YAML manifests
- Creating Merge Requests

This is more reliable, batches commits correctly (up to 20 files per API call), and handles `create` vs `update` actions correctly based on whether the file already exists in the target branch.

### The MCP subprocess client design

`tools/gitlab_mcp_tools.py` implements a full JSON-RPC 2.0 client over a subprocess pipe:

```python
class _MCPClient:
    def __init__(self):
        self._proc = None          # the npx subprocess
        self._lock = threading.Lock()  # one call at a time
        self._req_id = 0           # auto-incrementing request IDs

    def call_tool(self, name: str, arguments: dict) -> Any:
        with self._lock:
            self._start()          # lazy start — only spawns on first call
            self._req_id += 1
            self._write({"jsonrpc": "2.0", "id": self._req_id,
                         "method": "tools/call",
                         "params": {"name": name, "arguments": arguments}})
            return self._read_until_id(self._req_id)
```

The MCP server runs as a long-lived subprocess for the duration of the pipeline run. It is started lazily on the first call and terminated at process exit via `atexit.register`. The `threading.Lock()` prevents concurrent calls from interleaving their JSON-RPC messages.

### Why a subprocess, not an HTTP client?

The `@modelcontextprotocol/server-gitlab` package communicates over stdin/stdout (stdio transport), not HTTP. This is the standard MCP transport for local tool servers. An HTTP MCP server would require a separately deployed service — the stdio approach runs entirely within the ShiftLeft process.

---

## 6. Agent Design: Cartographer

### Purpose

Produce a complete, structured representation of the repository that the Triage agent can use without making additional API calls. The Cartographer is the only agent that touches the GitLab API for reading — all subsequent agents work from its output.

### Why Python AST over regex or LLM

Three approaches to "understand a Python file":

1. **Regex** — fragile, breaks on decorators, multiline strings, nested functions
2. **LLM** — expensive, slow, non-deterministic, and unnecessary: Python already ships a complete parser
3. **Python `ast` module** — the actual Python parser, zero dependencies, deterministic

The `ast` module produces a proper syntax tree. ShiftLeft walks it to extract:

```python
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef):
        # extract: name, args (with type annotations), return type, docstring, line numbers
    elif isinstance(node, ast.ClassDef):
        # extract: name, base classes, method names, line count
    elif isinstance(node, ast.Import) | isinstance(node, ast.ImportFrom):
        # extract: top-level module names
```

This gives Triage everything it needs: what functions exist, what they take, what they return, what they depend on — without sending the raw source to the LLM for the mapping step.

### Why not map every file with LLM?

Sending 32 files through Gemini for summarization would cost ~10× more tokens and take ~10× longer. The AST map is a lossless structural representation — better than any LLM summary because it captures the exact function signatures.

### File limits

```python
MAX_PY_FILES  = 35      # cap to avoid context window overflow in Triage
MAX_FILE_CHARS = 12_000 # truncate very large files (adds truncation comment)
```

The 35-file cap prevents the Triage prompt from exceeding Gemini's context window. In practice, most real repos have fewer than 35 meaningful source files (after excluding tests, docs, migrations).

### The YAML map

For each file, the Cartographer writes a YAML document to `yaml_map{}`:

```yaml
file: gitlab/_backends/requests_backend.py
last_analyzed: 2026-05-17_032905
loc: 124
imports: [requests, urllib3, logging]
functions:
  - name: http
    args: [self, "verb: str", "path: str", "**kwargs"]
    returns: requests.Response
    docstring: Execute an HTTP request against the GitLab API.
    loc: 31
```

This YAML is committed to the repo by HITL — it becomes the `.shiftleft/` knowledge base.

---

## 7. Agent Design: Triage

### The prompt design

The Triage prompt sends:
1. A formatted list of open GitLab issues (title + description, up to 10)
2. A formatted file map (file path + loc + functions + classes + imports for every file)

And asks for a single JSON object:

```json
{
  "severity": "critical|high|medium|low",
  "target_files": ["exactly/one/file.py"],
  "issue_summary": "One sentence max 100 chars",
  "root_cause": "2 sentences",
  "suggested_fix": "2 sentences",
  "related_issue_iid": null
}
```

### Why temperature 0.1?

Bug triage is a classification task, not a creative task. We want the most likely correct answer, not a diverse one. Temperature 0.1 makes the model nearly deterministic — running the same prompt 10 times produces the same result 9+ times.

### Why JSON output, not prose?

The output is machine-consumed, not human-consumed. Prose would require parsing; JSON can be `json.loads()`ed directly. The prompt explicitly forbids markdown fences and extra text. When the model produces fences anyway (it sometimes does), the parser strips them:

```python
if raw.startswith("```"):
    parts = raw.split("```")
    raw = parts[1].lstrip("json").strip()
```

### Fallback when JSON fails

If JSON parsing fails (rare, but network interruptions or model errors can produce garbled output), Triage falls back to the largest non-test file by line count:

```python
best = max(code_file_map.items(), key=lambda kv: kv[1].get("loc", 0))
result = {"severity": "medium", "target_files": [best[0]], ...}
```

The reasoning: the largest file has the most code, and is therefore statistically most likely to contain a bug worth fixing. This ensures the pipeline never stops on a JSON parse error.

### Skip patterns

```python
SKIP_TARGET_PATTERNS = (
    "docs/", "tests/", "test_", "migrations/", ".shiftleft/",
    "setup.py", "conf.py", "conftest.py",
)
```

These patterns prevent Triage from targeting documentation, test files, or the YAML maps themselves. A bug in a test file is not a production bug. The Cartographer also filters these out of the file map to reduce prompt size.

---

## 8. Agent Design: Coder

### The prompt design

The Coder prompt sends:
- The full source file content (up to 12,000 chars)
- The severity and issue summary from Triage
- On retry iterations: the failing diff from the previous attempt

And asks for the complete fixed file wrapped in a single code block:

```
Return the COMPLETE fixed file (not a diff, not a snippet — the ENTIRE file).
Wrap the entire file in a single ```python ... ``` block.
```

### Why the complete file, not a diff?

Three options for "give me the fix":

1. **Unified diff** — The model would need to produce exact line numbers and context. LLMs are notoriously bad at this — off-by-one errors in diffs are common, and an invalid diff cannot be applied.

2. **Code snippet** — Requires splicing the snippet back into the original file, which requires knowing exactly where it goes. Error-prone.

3. **Complete file** — The model returns the entire fixed file. The Auditor validates it. The HITL commits it directly. No splicing required.

The complete file approach is more tokens, but eliminates an entire class of bugs. The diff is generated programmatically by ShiftLeft:

```python
diff = "".join(difflib.unified_diff(
    original.splitlines(keepends=True),
    patched.splitlines(keepends=True),
    fromfile=f"a/{filepath}", tofile=f"b/{filepath}",
))
```

This diff is used in the MR description and in the retry context — not for applying the patch.

### Why temperature 0.15?

Code generation requires slightly more creativity than classification. Temperature 0.15 allows the model to choose between equivalent implementations without being fully deterministic. This is important for retry iterations — we need a *different* approach, not the same wrong one.

### Multi-language support

The Coder detects the file's language from its extension and injects it into the prompt:

```python
_EXT_LANG = {
    ".py": "python", ".js": "javascript", ".ts": "typescript",
    ".go": "go", ".rb": "ruby", ".java": "java", ".rs": "rust",
}
```

The prompt template uses `{language}` as the code fence language tag. This ensures the model produces language-appropriate output and the code extraction regex matches the right fence.

### The retry context injection

On iteration 2+, the Coder receives the failing diff:

```
## ⚠️ Previous fix FAILED the auditor
The diff that was rejected:
```diff
- def http(self, verb, path, **kwargs):
+ def http(self, verb: str, path: str, **kwargs) -> requests.Response:
```
Try a fundamentally different approach.
```

This is critical. Without failure context, the model often produces the same wrong fix. With it, the model understands the constraint space and converges quickly.

---

## 9. Agent Design: Auditor

### Why multi-layer validation?

A single syntax check is not enough. Consider:
- A file can be syntactically valid Python but semantically broken (wrong import path, undefined variable)
- A file can be valid but produce a diff with no changes (model returned the original file unchanged)

The Auditor runs these layers in order:

**Layer 1: Content check** — is the patched_content non-empty?

**Layer 2: Language-specific syntax check** — in a temp file, not in the repo

**Layer 3: Diff check** — warn if the diff is empty (patch unchanged the file)

**Layer 4: pytest** — only runs if test files exist in the patch set, in an isolated temp directory

### Why temp directories, not the actual repo?

The target repo is on GitLab — it's not cloned locally. ShiftLeft writes the patched file to a temp directory specifically for validation, runs the compiler there, and discards it. The temp directory approach:

1. Does not require cloning the full repo (saves time and auth complexity)
2. Is completely isolated — a bad patch cannot affect anything outside the temp dir
3. Allows multiple patches to be validated simultaneously if needed

### Why is pytest "best-effort"?

Running the full test suite requires the complete repo with all dependencies installed — something ShiftLeft explicitly avoids (no git clone). The Auditor runs pytest only on the patched file(s). This catches the most common failure: the patched file imports a module that doesn't exist. It won't catch integration failures that require the full codebase.

This is an intentional design decision. The MR is the human review step — the human runs the full test suite before merging. ShiftLeft's job is to produce a syntactically valid, non-obviously-broken fix.

### Why max 3 iterations?

Empirically, if a fix hasn't passed syntax validation in 3 attempts, one of two things is true:
1. The bug is more complex than a single-file fix can address
2. The model needs human guidance

In both cases, the right action is to open the MR anyway with the iteration count in the description, so a human engineer can see what was attempted and complete the fix manually. The MR is still useful — it has the bug diagnosis (Triage output) and the closest-attempt diff.

---

## 10. Agent Design: HITL

"Human in the Loop" — the final agent that surfaces the pipeline's output for human review.

### Why MCP for branch creation but REST for commits?

See [Section 5](#5-why-gitlab-mcp--rest-hybrid). Short answer: `create_branch` via MCP works reliably. `push_files` via MCP has an upstream JS bug.

### The commit batching strategy

The GitLab Commits API has a limit on the number of actions per commit. ShiftLeft batches in groups of 20:

```python
_COMMIT_BATCH = 20

for i in range(0, len(files), _COMMIT_BATCH):
    batch = files[i: i + _COMMIT_BATCH]
    # ... POST /repository/commits with batch actions
```

Source patches and YAML manifests are committed in **separate commits** intentionally:

1. `fix(high): Missing retry logic...` — the actual code change
2. `docs(shiftleft): YAML knowledge base — run_id` — the manifests

This keeps the git history clean — a reviewer can see exactly what was changed vs what is bookkeeping.

### Create vs update action detection

The GitLab Commits API requires specifying `"action": "create"` or `"action": "update"` for each file. Using the wrong action causes a 400 error. ShiftLeft pre-fetches the list of existing files in the default branch and compares:

```python
existing = _existing_paths(project, default_ref)
action = "update" if fp in existing else "create"
```

### The MR description as an audit log

The MR description is a structured audit record:

```markdown
| Field | Value |
|---|---|
| Run ID | `2026-05-17_032905` |
| Severity | **HIGH** |
| Tests | ✅ PASSED |
| LLM Backend | **Vertex AI** — `gemini-3.1-pro-preview` |
| GCP Project | `my-gcp-project` · `us-central1` |
| Orchestration | LangGraph (5-agent pipeline) |
```

Every time a judge opens the live MR, they see exactly which Google Cloud services produced the fix.

---

## 11. The State Schema

`core/state.py` defines the single shared state dictionary that flows through all agents:

```python
class ShiftLeftState(TypedDict, total=False):
    # Identity
    run_id:             str      # "2026-05-17_032905"
    repo_url:           str
    trigger_source:     str      # "streamlit" | "webhook" | "benchmark"
    gitlab_project_id:  str      # "user/repo"

    # Cartographer output
    open_issues:        List[Dict[str, Any]]
    file_map:           Dict[str, Any]   # filepath → AST summary
    yaml_map:           Dict[str, str]   # yaml_path → yaml content
    branch_name:        str              # "shiftleft/run-2026-05-17_032905"
    repo_local_path:    str              # always "" — no local clone

    # Triage output
    issue_summary:      str
    target_files:       List[str]
    severity:           str

    # Coder output
    patches:            List[Dict[str, Any]]  # PatchFile TypedDict
    iteration:          int                   # retry count

    # Auditor output
    test_results:       str
    tests_passed:       bool

    # HITL output
    pr_url:             str
    pr_number:          int
    changed_files:      List[str]
    diff_hunks:         List[Dict[str, Any]]
```

### Why TypedDict?

TypedDict gives static type checking without runtime overhead. `total=False` means all fields are optional — agents add fields to the state dict and return `{**state, "new_field": value}`. LangGraph merges these returns into the shared state automatically.

### Why a single flat state, not nested?

Nested state (e.g., `state["cartographer"]["file_map"]`) requires knowing the producing agent's name when consuming. A flat state means any agent can access any field without knowing who produced it. This also makes the state trivially serializable for logging and debugging.

---

## 12. The Retry Loop

The retry loop is the core technical differentiator of ShiftLeft over a simple linear pipeline.

```python
# core/graph.py
def route_after_audit(state: ShiftLeftState) -> str:
    if state.get("tests_passed"):
        return "hitl"
    if (state.get("iteration") or 0) >= MAX_ITERATIONS:
        return "hitl"   # open MR anyway — human reviews
    return "coder"      # retry with failure context
```

```python
workflow.add_conditional_edges(
    "auditor",
    route_after_audit,
    {"hitl": "hitl", "coder": "coder"},  # edge map
)
```

### What "retry with context" means

When the Auditor fails and routes back to the Coder, the Coder receives `state["patches"]` — which contains the previous failed patch including its diff. The Coder prompt for iteration 2+ includes:

```
## ⚠️ Previous fix FAILED the auditor
The diff that was rejected: [diff here]
Try a fundamentally different approach.
```

The model sees what it tried and why it failed. It cannot produce the same fix twice (or if it does, the Auditor catches it again and the loop continues to the 3-retry limit).

### Why the loop terminates even on failure

If the Auditor fails 3 times, the pipeline still opens an MR. This is intentional:

1. The MR description documents all 3 attempts
2. A human engineer gets the bug diagnosis (Triage output) for free
3. The closest-attempt diff is visible in the MR for the human to refine
4. The `.shiftleft/` audit log records the failure for post-mortem analysis

An autonomous system that silently gives up is worse than one that hands off gracefully.

---

## 13. The `.shiftleft/` Knowledge Base

Every run writes a structured YAML map of the codebase to the target repository. This is not just documentation — it is a **feedback loop**.

### The compounding accuracy effect

On the first run:
- Triage receives raw AST data — function names, classes, imports

On the second run:
- Triage receives AST data **plus** the `.shiftleft/map/` YAML from the previous run
- The YAML includes docstrings, historical context, and the previous audit log
- Triage can see what was fixed before and avoid targeting the same file

Over multiple runs, the repository builds a machine-readable self-understanding. The LLM's triage accuracy improves because the context becomes richer.

### Structure

```
.shiftleft/
├── config.yaml          # pipeline configuration (schedule, ignore patterns)
├── manifest.yaml        # run metadata (files analyzed, skipped, timestamp)
├── audits/
│   └── run_id.yaml      # severity, target, diff, test output, LLM backend, iteration count
└── map/
    └── module/
        └── file.yaml    # functions, classes, imports, loc, docstrings
```

### Why YAML, not JSON?

YAML is human-readable in the GitLab file browser. A developer can click on `.shiftleft/map/requests_backend.yaml` in the GitLab UI and immediately understand what ShiftLeft knows about that file. JSON would be functional but less readable.

---

## 14. Arize Phoenix Observability

`utils/tracing.py` initializes OpenInference instrumentation at process startup.

### What gets traced

Every call to `utils.llm.generate()` produces an OpenInference span with:
- `input.value` — the full prompt
- `output.value` — the model's response
- `llm.token_count.prompt` — input tokens
- `llm.token_count.completion` — output tokens
- `llm.model_name` — the model used
- Latency — wall-clock time for the API call

Every LangGraph node transition produces a span with the agent name and the state fields it modified.

### Why OpenInference over custom logging?

OpenInference is an open standard for LLM observability — the same format used by Arize Phoenix, LangSmith, and other LLM monitoring tools. Instrumenting with OpenInference means ShiftLeft's traces are portable — they can be exported to any OTLP-compatible backend, not just Arize.

Custom logging (e.g., writing token counts to a file) would only be readable by ShiftLeft's own tooling.

### The instrumentation chain

```python
# utils/tracing.py
from phoenix.otel import register
from openinference.instrumentation.vertexai import VertexAIInstrumentor
from openinference.instrumentation.langchain import LangChainInstrumentor

tracer_provider = register(api_key=ARIZE_API_KEY, project_name="shiftleft")
VertexAIInstrumentor().instrument(tracer_provider=tracer_provider)
LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
```

`VertexAIInstrumentor` monkey-patches the `vertexai` SDK to emit spans automatically. `LangChainInstrumentor` patches LangGraph's execution engine. No code changes are required in the agents themselves.

---

## 15. Cloud Run Deployment Model

### Why Cloud Run?

ShiftLeft's workload profile is: **completely idle for hours, then needs 2 vCPUs for 60 seconds**. Cloud Run is a perfect fit:

- Scales to zero between runs — zero cost when idle
- Spins up in < 1 second on incoming webhook
- No server management
- OIDC authentication built in (for Cloud Scheduler → Cloud Run calls)

### The webhook design

`cloud/web_hook.py` uses FastAPI with `BackgroundTasks`:

```python
@app.post("/webhook/gitlab/issue")
async def gitlab_issue_webhook(request: Request, background: BackgroundTasks):
    # 1. Verify token (fast — constant-time string compare)
    # 2. Check for "shiftleft" label (fast — dict lookup)
    # 3. Queue pipeline as background task
    background.add_task(_run_pipeline, pipeline_state)
    # 4. Return HTTP 200 immediately
    return JSONResponse({"queued": True, "run_id": ...})
```

GitLab webhooks have a 10-second timeout. If the endpoint doesn't respond within 10 seconds, GitLab marks the delivery as failed and retries. By returning immediately and running the pipeline in the background, ShiftLeft avoids false webhook failures.

### The auto-trigger flow

```
1. Developer labels GitLab issue "shiftleft"
2. GitLab fires POST to Cloud Run /webhook/gitlab/issue
3. Cloud Run verifies X-Gitlab-Token (constant-time compare)
4. Cloud Run checks: does payload.labels[] include "shiftleft"?
5. Cloud Run returns 200 {"queued": true}  [< 100ms]
6. Background: shiftleft_app.invoke(state)  [~57 seconds]
7. Background: GitLab MR opened
8. Developer receives GitLab MR notification
```

---

## 16. What Was Deliberately Not Built

Understanding what was excluded explains the architecture as much as what was included.

### No local git clone

ShiftLeft never clones the target repository. All file reads go through GitLab MCP or the GitLab REST API. Reasons:
- Cloning requires storing credentials for git operations
- A 700-file repo might take 10-30 seconds to clone
- Storage on Cloud Run is ephemeral and limited
- MCP + REST reads are more selective — only source files are fetched

Trade-off: ShiftLeft can only fix one file per run. Multi-file fixes require cloning. This is an acceptable trade-off for the 60-second target.

### No vector database or embeddings

Some agent systems embed code into a vector store for semantic search. ShiftLeft uses the Python AST instead. Reasons:
- AST parsing is exact — no semantic drift from embeddings
- No additional infrastructure (Pinecone, Weaviate, pgvector)
- No embedding cost
- No cold start delay for embedding model initialization

The AST gives Triage everything it needs: function names, signatures, dependencies — without approximate vector search.

### No streaming LLM output

The Coder and Triage agents use standard (non-streaming) Vertex AI calls. Reasons:
- The agents need the complete response before proceeding
- Streaming requires buffering the full response anyway for JSON parsing
- Complexity of streaming + retry is not worth it for 60-second total runtime

The Streamlit UI streams **logs** in real time (via `queue.Queue`) — not LLM output. This gives users live feedback without requiring streaming API calls.

### No persistent database

ShiftLeft stores all state in the LangGraph `ShiftLeftState` dict for the duration of a run. After the run, state is discarded. The only persistence is the `.shiftleft/` YAML committed to the target repo. Reasons:
- Cloud Run is stateless by design
- A database would add infrastructure complexity and cost
- The git history is the audit log — no separate database needed

---

*For setup instructions, see [SETUP.md](../SETUP.md). For the Devpost submission narrative, see [DEVPOST_STORY.md](DEVPOST_STORY.md).*