# ShiftLeft — Devpost Submission Story




## Inspiration

Every engineering team I've worked with has the same conversation: *"That bug's been open for three months."* Not because nobody cares. Not because the fix is hard. Because nobody has the four uninterrupted hours to context-switch into an unfamiliar part of the codebase, understand the issue, write the fix, test it, open a PR, and handle the review comments.

The bug backlog is not a motivation problem. It is a cognitive load problem.

I built ShiftLeft to eliminate the part of that loop that costs the most: getting from "issue exists" to "fix is ready for review." That gap — from labeled issue to open Merge Request — is what ShiftLeft closes. Automatically. In 60 seconds. While the engineer is doing something else.

The name comes from the DevSecOps principle of "shifting left" — catching problems earlier in the development cycle. ShiftLeft shifts bug fixing as early as possible: the moment an issue is labeled.

---

## What It Does

ShiftLeft is a 5-agent autonomous software engineering system built on Google Cloud.

When a developer adds the `shiftleft` label to any GitLab issue, a webhook fires to a Cloud Run service. The following happens automatically, without any human involvement:

**1. Cartographer** reads every source file in the repository using the GitLab MCP server. It AST-parses each Python file — extracting function signatures, class hierarchies, imports, and docstrings. It also fetches all open GitLab issues. The result is a structured YAML knowledge map of the entire codebase.

**2. Triage** sends the complete codebase map and issue list to Gemini 2.0 Flash running on Vertex AI. Gemini identifies the single highest-severity bug — matching open issues where possible, falling back to static analysis of the code structure.

**3. Coder** sends the full content of the target file to Gemini on Vertex AI with the bug summary. Gemini returns the complete fixed file — not a snippet, not a patch suggestion — the whole file, ready to commit.

**4. Auditor** validates the fix using language-native tools: `py_compile` for Python, `node --check` for JavaScript, `tsc --noEmit` for TypeScript, `go vet` for Go. If validation fails, the Coder is called again with the failing diff injected as context — up to three retries.

**5. HITL (Human in the Loop)** creates a branch using GitLab MCP, commits the patched file and the YAML knowledge base via the GitLab REST API, and opens a Merge Request with a full audit log.

**Total time: 57 seconds average. Cost: < $0.01 per run.**

Every LLM call is traced end-to-end in Arize Phoenix with token counts and latency per agent.

---

## How We Built It

### Orchestration: LangGraph

The pipeline is modeled as a directed cyclic graph using LangGraph. The key insight is that a linear pipeline is insufficient — the Auditor needs to be able to send control back to the Coder when validation fails. LangGraph's conditional edge makes this declarative:

```python
def route_after_audit(state) -> str:
    if state["tests_passed"]:      return "hitl"
    if state["iteration"] >= 3:    return "hitl"   # hand off to human
    return "coder"                                  # retry with context
```

We chose LangGraph over CrewAI and AutoGen because ShiftLeft's agents don't converse — they transform structured data. LangGraph's typed state machine model is a better fit than conversation-based frameworks.

### LLM: Gemini on Vertex AI

All LLM calls use `vertexai.GenerativeModel` from the `google-cloud-aiplatform` SDK. Authentication uses Application Default Credentials in development and a service account in Cloud Run — no API keys in production.

We built a single abstraction layer (`utils/llm.py`) that all agents call. This makes swapping between Vertex AI and AI Studio a one-line config change, and is where Arize instrumentation hooks in.

### GitLab Integration: MCP + REST Hybrid

ShiftLeft uses both the GitLab MCP server (`@modelcontextprotocol/server-gitlab`) and the GitLab REST API. MCP handles branch creation and file reads — satisfying the hackathon's MCP integration requirement. The REST API handles file commits and MR creation, where we need precise control over batch size and create-vs-update action selection.

The MCP client is a full JSON-RPC 2.0 implementation over a subprocess pipe, built entirely in Python without any MCP client library dependency.

### Code Understanding: Python AST

Rather than sending source files to an LLM for summarization (expensive and slow), ShiftLeft uses Python's built-in `ast` module to parse every file. This produces exact function signatures, class hierarchies, and dependency graphs — more accurate than any LLM summary, at zero cost.

### Observability: Arize Phoenix

`utils/tracing.py` initializes OpenInference instrumentation at startup. `VertexAIInstrumentor` and `LangChainInstrumentor` automatically trace every LLM call and every LangGraph node without any changes to the agent code. Traces are exported via OTLP to Arize Phoenix Cloud.

---

## Challenges We Ran Into

**The MCP push_files bug.** The `@modelcontextprotocol/server-gitlab` npm package has a JavaScript bug in its `push_files` implementation — it calls `.map()` on a value that is sometimes `undefined` when committing multiple files. We discovered this after building our entire commit flow around MCP. The solution was to implement direct REST API calls for file commits while keeping MCP for the operations that work reliably (branch creation, file reads).

**JSON reliability from LLMs.** The Triage agent needs a specific JSON schema from Gemini. LLMs occasionally produce markdown-fenced JSON, trailing commas, or extra explanation text. We built a multi-layer extraction: strip markdown fences, attempt JSON parse, fall back to a deterministic heuristic (largest non-test file) if parsing fails. The fallback means the pipeline never stops on a JSON error.

**The retry context problem.** On the first retry, without telling the Coder what went wrong, Gemini often produces the same fix. Injecting the failing diff as "this is what not to do" dramatically improved second-attempt success rates. The fix was simple but required recognizing that the problem was information loss between iterations.

**Vertex AI authentication in Cloud Run.** Local development with `gcloud auth application-default login` is seamless, but Cloud Run requires a service account with `roles/aiplatform.user`. Setting this up correctly — and writing clear documentation for it — took significant iteration.

**Webhook timing.** GitLab webhooks time out after 10 seconds. The pipeline takes ~60 seconds. The solution is FastAPI's `BackgroundTasks` — return HTTP 200 immediately, run the pipeline as a non-blocking background task. This was straightforward once identified, but caused confusing "webhook delivery failed" errors during early testing.

---

## Accomplishments We're Proud Of

**A working end-to-end system.** Not a demo. Not a mock. ShiftLeft has fixed a real bug in a real public GitLab repository ([see MR !2](https://gitlab.com/amareshhebbar/python-gitlab-forktesting/-/merge_requests/2)), and the MR is open for anyone to review. The diff is real. The branch is real. The commit history is real.

**The retry loop with failure context injection.** This is the technical detail that makes the system reliable. Without it, a failed syntax check would permanently break the pipeline. With it, the Coder receives the exact diff that failed and generates a genuinely different approach.

**The `.shiftleft/` knowledge base.** Every run builds on the previous one. The repository builds a structured, machine-readable self-understanding over time. On the fifth run, the LLM has four previous audit logs, YAML maps of every file, and a history of what was fixed — triage accuracy compounds.

**Sub-$0.01 cost per run.** Averaging ~17,000 tokens (1 triage + 1 code call on Gemini 2.0 Flash via Vertex AI), each ShiftLeft run costs less than one cent. A 10-person team with 20 bug-labeled issues per week automates roughly 40 engineering-hours of work for under $2/week.

**100% triage accuracy across 5 test repositories.** In every benchmark run, ShiftLeft targeted the correct file — the one where a human engineer would have looked first. This validates the AST-based file map approach over LLM summarization.

---

## What We Learned

**The AST is better than LLM summarization for code structure.** We initially considered summarizing each file with Gemini before triage. The AST approach is faster, cheaper, more accurate, and deterministic. For structural analysis of code, the existing parser is always the right tool.

**Abstraction layers matter more than they seem.** `utils/llm.py` was added after the initial build when we needed to switch from AI Studio to Vertex AI. Adding it required updating every agent file. After the refactor, switching backends takes one config change. This lesson — build the abstraction before you need it — applies broadly.

**Return HTTP 200 first, run work in the background.** Every webhook-driven system should do this. GitLab's 10-second webhook timeout was not in the forefront of our minds during initial development, and the resulting "delivery failed" errors were confusing until we understood the cause.

**Observability is not optional in multi-agent systems.** Without Arize Phoenix tracing, debugging why a particular run took 78 seconds instead of 57 required grepping logs. With tracing, you can see exactly which LLM call was slow and what the input was. For any autonomous system with multiple LLM calls, observability should be day-one infrastructure.

**Failure handling is product design.** The decision to open an MR even when the Auditor fails (after 3 retries) was a product decision, not a technical one. An autonomous system that silently fails is worse than one that hands off gracefully with context. The MR with a failing diff and a bug diagnosis is still more useful than no MR at all.

---

## What's Next

**Multi-file fixes.** Currently ShiftLeft fixes one file per run. Many bugs span multiple files. The next version would use a local clone (ephemeral Cloud Run storage) to enable multi-file patches with cross-file import validation.

**Language expansion.** The Coder supports multiple languages, but the Cartographer only AST-parses Python. Adding Tree-sitter for JavaScript/TypeScript/Go AST parsing would extend the full triage pipeline to all major languages.

**PR comments and iteration.** After the MR is opened, a human reviewer might comment "you forgot to handle the edge case where X". The next version would read MR comments as additional context and submit revised commits in response.

**Automatic triage from CI failures.** Instead of waiting for a labeled issue, ShiftLeft could watch failing CI pipelines, extract the error from the test output, and attempt an autonomous fix — closing the loop from "CI red" to "fix committed" without any developer action.

**Team analytics dashboard.** The `.shiftleft/audits/` YAML files contain structured data about every run. A team dashboard showing "bugs fixed this week", "most-fixed files", and "average fix cost" would make the value of ShiftLeft visible to engineering managers.

---

## Built With

`python` `langgraph` `google-cloud-aiplatform` `vertexai` `google-cloud-run` `google-cloud-scheduler` `gitlab-mcp` `arize-phoenix` `openinference` `opentelemetry` `fastapi` `streamlit` `httpx` `pyyaml`

---

## Links

- **GitHub:** https://github.com/amareshhebbar/ShiftLeft
- **Live Demo (Streamlit):** https://shiftleft.streamlit.app
- **Live MR Proof:** https://gitlab.com/amareshhebbar/python-gitlab-forktesting/-/merge_requests/2
- **Demo Video:** https://youtu.be/0qyFCHWVS6g
- **Architecture Deep Dive:** [docs/ARCHITECTURE.md](ARCHITECTURE.md)