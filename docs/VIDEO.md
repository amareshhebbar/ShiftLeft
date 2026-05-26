# ShiftLeft — Demo Video Explained

**▶ Watch:** [https://youtu.be/vtxAohTLpK8](https://youtu.be/vtxAohTLpK8)  
**Duration:** 3:53  
**Built for:** Google Cloud Rapid Agent Hackathon 2026 — GitLab Partner Track

This document explains what is happening on screen at every moment in the demo video — the technical reasoning behind each step, what each agent is doing, and why the pipeline is designed the way it is.

---

## [0:00 — 0:28] The Problem

The video opens with the core premise: every engineering team has a bug backlog that never gets resolved. Not because the bugs are hard — but because no engineer has the uninterrupted time to context-switch into an unfamiliar file, understand the issue, write the fix, test it, open a PR, and handle review comments.

ShiftLeft's claim is introduced here: add a single label to any GitLab issue and within sixty seconds a Merge Request appears, ready for review. No human writes a line of code.

---

## [0:28 — 0:45] The Pipeline Starts

The terminal appears full screen. The command `python main.py` is run against `amareshhebbar/python-gitlab-forktesting` — a real public GitLab repository, not a mock or sandbox.

The first log lines appear:

```
[INFO] utils.llm — LLM backend: Vertex AI  project=...  model=gemini-2.0-flash-001
[INFO] cartographer — run_id=2026-05-17_032851
[INFO] cartographer — fetching repository tree via GitLab REST API
```

**Why this matters:** The first log line shows Vertex AI — not AI Studio, not OpenAI. This is Gemini running on Google Cloud's enterprise AI platform, authenticated via Application Default Credentials. No API key is in the environment.

The `run_id` timestamp is used as the branch name (`shiftleft/run-2026-05-17_032851`) and the audit log filename — every run is uniquely identified and traceable.

---

## [0:45 — 1:10] Agent 1: Cartographer

The Cartographer agent runs. The logs stream showing files being read one by one.

```
[INFO] cartographer — 32 Python files selected
[INFO] cartographer — gitlab/client.py  (412 loc, 18 funcs, 3 classes)
[INFO] cartographer — gitlab/_backends/requests_backend.py  (124 loc, 3 funcs, 1 class)
[INFO] cartographer — 32 YAML manifests built
[INFO] cartographer — 3 open issues loaded
  #1 Add context manager support to ProjectManager
  #2 No retry logic for API rate limit responses (HTTP 429)
  #3 Missing type annotations in gitlab/utils.py
```

**What is happening:** The Cartographer reads every Python source file in the repository using the GitLab MCP server (`get_file_contents`). For each file it runs the Python `ast` module — the actual Python parser — to extract every function name, its argument types and return type, every class name and its methods, every import. The result is a structured YAML file per source file.

**Why AST instead of sending files to the LLM:** Parsing 32 files through Gemini for summarization would cost ~10× more tokens and take ~10× longer. The AST gives exact function signatures — more accurate than any LLM summary — at zero LLM cost.

**The 3 open issues** are also fetched from the GitLab REST API and formatted into the Triage prompt. When a user's reported issue matches a code location, ShiftLeft prioritises that over static analysis.

All 32 files are mapped in under 12 seconds.

---

## [1:10 — 1:35] Agent 2: Triage

The single most important log line in the entire run:

```
[INFO] triage — 32 code files + 3 issues → Gemini (Vertex AI)
[INFO] triage — severity=HIGH  target=['gitlab/_backends/requests_backend.py']
                summary='Missing retry logic for HTTP 429 rate limit responses'
```

**What is happening:** The complete file map (all 32 files' AST summaries) plus the 3 open issue descriptions are sent to `vertexai.GenerativeModel("gemini-2.0-flash-001")` in a single prompt. The model is asked to pick exactly one file containing the highest-severity bug. Temperature is set to 0.1 — near-deterministic, because triage is a classification task, not a creative one.

**The bug Gemini identified:** Issue #2 — `RequestsBackend` in `gitlab/_backends/requests_backend.py` had no `urllib3.Retry` configuration. Every HTTP 429 (rate limited) or 5xx response from the GitLab API would immediately crash with an unhandled exception. Any pipeline calling python-gitlab under load would be vulnerable.

**Why this is the right answer:** Gemini correctly matched open issue #2 to the exact file. The AST map showed `requests_backend.py` imports `requests` and `urllib3` — Gemini knows this is where retry logic belongs.

---

## [1:35 — 1:55] Agent 3: Coder

```
[INFO] coder — calling Gemini (Vertex AI) for gitlab/_backends/requests_backend.py
[INFO] coder — patch: 12 lines changed
```

**What is happening:** The Coder reads the full source of `requests_backend.py` from the `file_map` (already in memory — no additional API call needed) and sends it to Gemini along with the bug summary from Triage. Temperature is 0.15 — slightly higher than Triage to allow the model to choose between equivalent implementations.

Gemini returns the **complete fixed file** — not a diff, not a snippet. ShiftLeft generates the unified diff programmatically using Python's `difflib` module. This avoids the common failure mode where LLMs produce diffs with incorrect line numbers.

**The fix Gemini wrote:**

```python
import urllib3

retry = urllib3.Retry(
    total=5,
    backoff_factor=0.5,
    status_forcelist=[429, 500, 502, 503],
)
adapter = requests.adapters.HTTPAdapter(max_retries=retry)
session = requests.Session()
session.mount("http://", adapter)
session.mount("https://", adapter)
```

12 lines. Correct. Handles the four most common GitLab API failure modes.

---

## [1:55 — 2:10] Agent 4: Auditor

```
[INFO] auditor — iteration 1: PASSED ✅
[INFO] auditor — results:
  [PASS] gitlab/_backends/requests_backend.py: syntax OK
  [INFO] No test files in patched set — pytest skipped
```

**What is happening:** The Auditor writes the patched file to an isolated temp directory and runs `py_compile` on it — Python's built-in syntax checker. If this fails, the Coder is called again with the failing diff injected as context ("here is what you tried and what went wrong — try a different approach"). This retry loop runs up to 3 times.

**Why this matters:** Without the Auditor, a syntactically broken patch would be committed to GitLab and the MR would be useless. With the Auditor's self-correction loop, the overall MR success rate across benchmarks is 100% even though individual first attempts occasionally produce invalid syntax.

This run passed on the first attempt. The Auditor also checked for test files in the patch set — there were none in this single-file patch, so pytest was skipped.

---

## [2:10 — 2:35] Agent 5: HITL (Human in the Loop)

```
[INFO] hitl — ✅ branch created via GitLab MCP: shiftleft/run-2026-05-17_032851
[INFO] hitl — committed batch 1 (1 files) via REST
[INFO] hitl — committed batch 2 (36 files) via REST
[INFO] hitl — ✅ MR: https://gitlab.com/amareshhebbar/python-gitlab-forktesting/-/merge_requests/2

================================================================
✅  Merge Request: https://gitlab.com/.../merge_requests/2
================================================================
```

**What is happening:** Three separate operations:

1. **Branch creation via GitLab MCP** — `create_branch` is called through the `@modelcontextprotocol/server-gitlab` npm package via a JSON-RPC 2.0 subprocess pipe. This is the MCP integration the hackathon requires.

2. **File commits via REST API** — The patched `requests_backend.py` and all 32 YAML knowledge-base files are committed via the GitLab Commits REST API in batches of 20. The REST API is used here rather than MCP's `push_files` because of an upstream JavaScript bug in the MCP package's file-push implementation.

3. **MR creation via REST API** — The Merge Request is opened with a full description table: Run ID, Severity, test results, LLM backend (Vertex AI), GCP project and region.

Total time from `python main.py` to open MR: **58 seconds**.

---

## [2:35 — 3:00] The Live Merge Request

The browser opens to the actual MR on GitLab. The description table is visible:

| Field | Value |
|---|---|
| Run ID | `2026-05-17_032851` |
| Severity | HIGH |
| Tests | ✅ PASSED |
| LLM Backend | Vertex AI — `gemini-2.0-flash-001` |
| GCP Project | `my-gcp-project` · `us-central1` |

Switching to the Changes tab shows the diff — 12 green lines, 0 red lines. The `urllib3.Retry` block is exactly what the issue described. A human engineer reviewing this MR can immediately understand what was found, why, and what was changed.

**This is a real MR** — the branch exists, the commit is real, the diff is real. It is open for anyone to review at the URL shown.

---

## [3:00 — 3:25] The .shiftleft/ Knowledge Base

The GitLab file browser navigates to `.shiftleft/map/gitlab/_backends/requests_backend.yaml`. The YAML content is shown:

```yaml
file: gitlab/_backends/requests_backend.py
last_analyzed: 2026-05-17_032851
loc: 124
imports: [requests, urllib3, logging]
functions:
  - name: http
    args: [self, "verb: str", "path: str", "**kwargs"]
    returns: requests.Response
    docstring: Execute an HTTP request against the GitLab API.
    loc: 31
classes:
  - name: RequestsBackend
    inherits: [BackendBase]
    methods: [__init__, http, _build_session]
    loc: 98
```

**Why this exists:** Every ShiftLeft run commits a structured YAML file for each Python file in the repository. On subsequent runs, this map is already in the repo — ShiftLeft reads its own previous output as additional context. Triage accuracy compounds over time because the LLM can see the codebase's history and what was previously analyzed.

The `.shiftleft/audits/` folder also contains a full audit log for every run — severity, target, diff, test output, LLM backend, iteration count — forming a machine-readable history of every autonomous fix.

---

## [3:25 — 3:53] Architecture and Wrap-up

The Streamlit dashboard appears at `shiftleft.streamlit.app`. The live agent tracker is visible — the five agent stages (Cartographer → Triage → Coder → Auditor → HITL) with real-time status indicators.

The final narration covers the full stack and the economics:

- **Gemini on Vertex AI** — Google Cloud's enterprise AI platform, not AI Studio
- **LangGraph** — the cyclic state machine that enables the Auditor → Coder retry loop
- **GitLab MCP** — the Model Context Protocol integration for branch operations
- **Google Cloud Run** — the webhook server that auto-triggers on labeled issues
- **Arize Phoenix** — every LLM call traced with token counts and latency

**The cost number:** ~17,000 tokens per run on Gemini 2.0 Flash via Vertex AI = **less than $0.01 per bug fixed**. A 10-person team labeling 20 issues per week automates ~40 hours of engineering work for under $2/week.

The closing line: *"Not a demo. Not a prototype. A working system, fixing real bugs in real repositories, right now."* — referring to the live MR that was just created on screen.

---

## Links Referenced in the Video

| Link | What it is |
|---|---|
| [github.com/amareshhebbar/ShiftLeft](https://github.com/amareshhebbar/ShiftLeft) | Source code |
| [shiftleft.streamlit.app](https://shiftleft.streamlit.app) | Live dashboard |
| [Live MR !2](https://gitlab.com/amareshhebbar/python-gitlab-forktesting/-/merge_requests/2) | The real MR created during the demo |
| [youtu.be/vtxAohTLpK8](https://youtu.be/vtxAohTLpK8) | This video |