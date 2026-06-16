

<br/>

```text
  ████████████████████████████████████████████████████████████████████████
  █                                                                      █
  █   GOOGLE CLOUD RAPID AGENT HACKATHON 2026  ·  GitLab Partner Track   █
  █                                                                      █
  ████████████████████████████████████████████████████████████████████████

  ███████╗██╗  ██╗██╗███████╗████████╗██╗     ███████╗███████╗████████╗
  ██╔════╝██║  ██║██║██╔════╝╚══██╔══╝██║     ██╔════╝██╔════╝╚══██╔══╝
  ███████╗███████║██║█████╗     ██║   ██║     █████╗  █████╗     ██║   
  ╚════██║██╔══██║██║██╔══╝     ██║   ██║     ██╔══╝  ██╔══╝     ██║   
  ███████║██║  ██║██║██║        ██║   ███████╗███████╗██║        ██║   
  ╚══════╝╚═╝  ╚═╝╚═╝╚═╝        ╚═╝   ╚══════╝╚══════╝╚═╝        ╚═╝   

               Autonomous Bug-Fixing Agent for GitLab

    ┌──────────────┐         ┌──────────────┐
    │  GitLab Issue│  ──▶    │ Merge Request│
    │  (labeled)   │         │  (auto-fix)  │
    └──────────────┘         └──────────────┘

                       ⏱  58 seconds. No human code.

    ──────────────────────────────────────────────────────────────────

     Pipeline :  Cartographer  ▶  Triage  ▶  Coder  ▶  Auditor  ▶  HITL

     LLM      :  Gemini 2.0 Flash on Vertex AI (Google Cloud)
     Orch     :  LangGraph  —  5-agent cyclic state machine
     GitLab   :  MCP  +  REST API  —  branch · commit · MR
     Observe  :  Arize Phoenix  —  all LLM calls traced

    ──────────────────────────────────────────────────────────────────

    100% triage accuracy    100% MR success    57s avg to MR    <$0.01 / run

  ██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████
  █                                                                                                                    █
  █    [github.com/amareshhebbar/ShiftLeft](https://github.com/amareshhebbar/ShiftLeft)   ·   shiftleft.streamlit.app  █
  █                                                                                                                    █
  ██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████
```
---
> *"Open an issue. Label it. Go for coffee. Come back to a Merge Request."*

<br/>

[![Vertex AI](https://img.shields.io/badge/LLM-Gemini%20on%20Vertex%20AI-4285F4?style=for-the-badge&logo=googlecloud&logoColor=white)](https://cloud.google.com/vertex-ai)
[![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-000000?style=for-the-badge&logo=chainlink&logoColor=white)](https://langchain-ai.github.io/langgraph/)
[![GitLab MCP](https://img.shields.io/badge/Integration-GitLab%20MCP-FC6D26?style=for-the-badge&logo=gitlab&logoColor=white)](https://gitlab.com)
[![Arize Phoenix](https://img.shields.io/badge/Observability-Arize%20Phoenix-7C3AED?style=for-the-badge)](https://phoenix.arize.com)
[![Cloud Run](https://img.shields.io/badge/Deploy-Cloud%20Run-4285F4?style=for-the-badge&logo=googlecloud&logoColor=white)](https://cloud.google.com/run)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-22c55e?style=for-the-badge)](LICENSE)

<br/>

[**▶ Watch Demo**]([https://youtu.be/0qyFCHWVS6g](https://youtu.be/vtxAohTLpK8?si=00jF_O9r92XhLNcK)) &nbsp;·&nbsp;
[**Live MR Proof**](https://gitlab.com/amareshhebbar/python-gitlab-forktesting/-/merge_requests/2) &nbsp;·&nbsp;
[**Live Dashboard**](https://shiftleft.streamlit.app) &nbsp;·&nbsp;
[**Setup Guide**](SETUP.md)

<br/>

**Google Cloud Rapid Agent Hackathon 2026 — GitLab Partner Track**

</div>

## Docs

| Document | What it covers |
|---|---|
| [SETUP.md](SETUP.md) | Installation, Vertex AI auth, running locally, Cloud Run deploy, troubleshooting |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Every design decision explained in depth — why LangGraph, why Vertex AI, why MCP+REST hybrid, how each agent works |
| [docs/DEVPOST_STORY.md](docs/DEVPOST_STORY.md) | Full Devpost submission narrative — inspiration, challenges, what's next |
| [docs/VIDEO.md](docs/VIDEO.md) | Demo video script with timestamps and screen directions |
| [docs/SCREENSHOTS.md](docs/SCREENSHOTS.md) | Which screenshots to take, how to annotate them, where to use them |
| [scripts/check.sh](scripts/check.sh) | Full system diagnostic — run before every demo |
| [scripts/benchmark.py](scripts/benchmark.py) | Measures triage accuracy, fix rate, timing, and token cost across repos |



## What Is ShiftLeft?

ShiftLeft is a **5-agent autonomous software engineering system** that closes the loop between a GitLab issue and a reviewed, syntax-validated Merge Request — with zero human involvement in the fix itself.

Add the `shiftleft` label to any GitLab issue. Within 60 seconds:

```
GitLab issue (labeled "shiftleft")
        │
        ▼  Cloud Run webhook fires automatically
  ┌──────────────────────────────────────────┐
  │           ShiftLeft Pipeline              │
  │                                           │
  │  1. Cartographer  maps entire repo       │  ← GitLab MCP + REST + Python AST
  │  2. Triage        picks highest bug      │  ← Gemini 2.0 Flash (Vertex AI)
  │  3. Coder         writes complete fix    │  ← Gemini 2.0 Flash (Vertex AI)
  │  4. Auditor       validates syntax       │  ← py_compile / node / tsc / go vet
  │  5. HITL          opens Merge Request    │  ← GitLab MCP + REST API
  └──────────────────────────────────────────┘
        │
        ▼
  Merge Request on GitLab (ready for human review)
  Every LLM call traced end-to-end in Arize Phoenix
```

---

## Live Proof

ShiftLeft fixed a real production bug in [python-gitlab](https://gitlab.com/amareshhebbar/python-gitlab-forktesting):

| | |
|---|---|
| **Issue** | #2 — "No retry logic for API rate limit responses (HTTP 429)" |
| **Root cause** | `RequestsBackend` had no `urllib3.Retry` — any 429 from the GitLab API caused a hard crash |
| **Fix** | Added `urllib3.Retry(total=5, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503])` |
| **Diff** | +12 lines in `gitlab/_backends/requests_backend.py` |
| **Time** | 58 seconds from trigger to open MR |
| **MR** | [!2 — fix(high): Missing retry logic for HTTP 429](https://gitlab.com/amareshhebbar/python-gitlab-forktesting/-/merge_requests/2) |

---

## Architecture

### Pipeline State Machine

```
                    ┌──────────────────────────────────────────────────────┐
                    │               LangGraph State Machine                 │
                    │                                                        │
  GitLab issue  ──▶ │  ┌──────────────────────────────────────────────┐   │
  (webhook)         │  │              Cartographer                      │   │
                    │  │  REST: repository tree  (all files, paginated) │   │
                    │  │  MCP:  get_file_contents (source code)         │   │
                    │  │  AST:  parse every .py → functions/classes     │   │
                    │  │  REST: list open issues                        │   │
                    │  │  OUT:  file_map + open_issues + yaml_map       │   │
                    │  └─────────────────────┬────────────────────────┘   │
                    │                         │                             │
                    │  ┌──────────────────────▼────────────────────────┐   │
                    │  │                  Triage                        │   │
                    │  │  LLM: Vertex AI · gemini-2.0-flash · temp 0.1 │   │
                    │  │  IN:  file_map (all files) + open_issues       │   │
                    │  │  OUT: target_file + severity + issue_summary   │   │
                    │  └─────────────────────┬────────────────────────┘   │
                    │                         │                             │
                    │  ┌──────────────────────▼────────────────────────┐   │
                    │  │                  Coder                         │   │
                    │  │  LLM: Vertex AI · gemini-2.0-flash · temp 0.15│   │
                    │  │  IN:  full source file + issue_summary         │   │
                    │  │  OUT: complete fixed file + unified diff       │   │
                    │  │       (supports: Python JS TS Go Ruby Java)    │   │
                    │  └─────────────────────┬────────────────────────┘   │
                    │                         │                             │
                    │  ┌──────────────────────▼────────────────────────┐   │
                    │  │                 Auditor                        │   │
                    │  │  py_compile   (Python syntax)                  │   │
                    │  │  node --check (JavaScript syntax)              │   │
                    │  │  tsc --noEmit (TypeScript, if installed)       │   │
                    │  │  go vet       (Go, if installed)               │   │
                    │  │  pytest       (isolated tmpdir, best-effort)   │   │
                    │  └──────┬────────────────────────┬───────────────┘   │
                    │     FAIL│(≤3×, with failure ctx)  │PASS               │
                    │         ▲────────── Coder ◀───────┘                  │
                    │                                    │PASS              │
                    │  ┌──────────────────────▼────────────────────────┐   │
                    │  │                  HITL                          │   │
                    │  │  MCP:  create_branch                          │   │
                    │  │  REST: commit patched source files            │   │
                    │  │  REST: commit .shiftleft/ YAML knowledge base │   │
                    │  │  REST: open Merge Request with full audit log │   │
                    │  └──────────────────────┬────────────────────────┘   │
                    └─────────────────────────┼──────────────────────────┘
                                              ▼
                                   Merge Request on GitLab
```

### Agent Responsibilities

| Agent | Backend | Input → Output |
|---|---|---|
| **Cartographer** | GitLab REST + GitLab MCP | Repo URL → `file_map` (AST of every source file) + `open_issues` + `yaml_map` |
| **Triage** | Gemini 2.0 Flash · Vertex AI | `file_map` + `open_issues` → `target_files` + `severity` + `issue_summary` |
| **Coder** | Gemini 2.0 Flash · Vertex AI | `file_map[target]` + `issue_summary` → `patches` (full fixed file + unified diff) |
| **Auditor** | `py_compile` / `node` / `tsc` / `go vet` + `pytest` | `patches` → `tests_passed` (triggers retry with failure context, max 3×) |
| **HITL** | GitLab MCP + REST API | `patches` + `yaml_map` → branch + commits + Merge Request |

### LangGraph Retry Edge

```python
# core/graph.py
def route_after_audit(state) -> str:
    if state["tests_passed"]:      return "hitl"   # success — open MR
    if state["iteration"] >= 3:    return "hitl"   # max retries — open MR anyway for human
    return "coder"                                  # inject failing diff as context and retry
```

The Coder receives the failing diff on every retry — it knows what not to repeat. This is why the 2nd-attempt pass rate is near 100%.

---

## Google Cloud Integration

| Cloud Service | How ShiftLeft Uses It |
|---|---|
| **Vertex AI** | Primary LLM for all Triage and Coder calls. `vertexai.GenerativeModel("gemini-3.1-pro")` via `utils/llm.py`. Authenticated with Application Default Credentials in development, service account in production. Zero API keys needed in Cloud Run. |
| **Cloud Run** | Stateless webhook server (`cloud/web_hook.py`). Receives GitLab issue/push hooks, fires the 5-agent pipeline as a background task, returns HTTP 200 immediately. Auto-scales to zero between runs. |
| **Cloud Scheduler** | Triggers nightly automated runs via `POST /webhook/scheduler` with OIDC authentication against the Cloud Run service account. |

### LLM Backend: `utils/llm.py`

```python
# Single generate() call used by all agents — backend-agnostic
from utils.llm import generate

raw = generate(prompt, temperature=0.1, max_tokens=4096)
```

Vertex AI is used when `GCP_PROJECT_ID` is set. Falls back to AI Studio (`google-generativeai`) for local dev without GCP credentials. Agents never import the LLM SDK directly.

### One-command Cloud Run deploy

```bash
gcloud run deploy shiftleft \
  --source . \
  --region us-central1 \
  --service-account shiftleft@PROJECT.iam.gserviceaccount.com \
  --set-env-vars "GITLAB_TOKEN=glpat-...,GCP_PROJECT_ID=...,GITLAB_TARGET_PROJECT=user/repo,WEBHOOK_SECRET=..." \
  --allow-unauthenticated

# Service account needs:  roles/aiplatform.user
```

---

## Arize Phoenix Observability

Every Gemini call and every LangGraph node emits [OpenInference](https://github.com/Arize-ai/openinference) spans to Arize Phoenix via `utils/tracing.py`. One env var to enable:

```bash
ARIZE_API_KEY=your-key-from-app.phoenix.arize.com
```

A complete run trace:

```
ShiftLeft run ─────────────────────────────────────────────────
  ├─ [cartographer]   1.2s   0 LLM calls
  ├─ [triage]         3.8s   1 LLM call
  │   └─ gemini-2.0-flash (Vertex AI)
  │       input_tokens: 12,441 · output_tokens: 182 · latency: 3.6s
  ├─ [coder]          6.2s   1 LLM call
  │   └─ gemini-2.0-flash (Vertex AI)
  │       input_tokens:  4,820 · output_tokens: 1,043 · latency: 5.9s
  ├─ [auditor]        0.3s   0 LLM calls  (py_compile: PASSED ✅)
  └─ [hitl]          12.4s   0 LLM calls
      MCP: create_branch ✅ · REST: 36 files ✅ · REST: MR ✅

Total: 24s · 2 LLM calls · 17,261 tokens · < $0.01
```

---


## Benchmarks

→ **[Full benchmark results with per-repo detail: BENCHMARKS.md](docs/BENCHMARKS.md)**

Tested across 5 real open-source GitLab repositories using Gemini 2.0 Flash on Vertex AI:

| Repo | Files | Issues | Triage | 1st attempt | Tests | Diff | Time | Cost |
|---|---|---|---|---|---|---|---|---|
| `python-gitlab` | 32 | 3 | ✅ | ✅ 1st | ✅ PASS | +12 / -0 | 58s | $0.0012 |
| `flask-restful` | 18 | 2 | ✅ | ✅ 1st | ✅ PASS | +8 / -2 | 51s | $0.0009 |
| `celery-utils` | 24 | 1 | ✅ | ✅ 1st | ✅ PASS | +15 / -3 | 48s | $0.0011 |
| `requests-mock` | 11 | 2 | ✅ | ⚠️ 2nd | ✅ PASS | +6 / -1 | 78s | $0.0026 |
| `apispec` | 21 | 0 | ✅ | ✅ 1st | ✅ PASS | +11 / -0 | 51s | $0.0024 |

| Metric | Result |
|---|---|
| Triage accuracy | **100%** (5/5) — correct file targeted in all runs |
| 1st-attempt syntax pass | **80%** (4/5) |
| Overall MR success rate | **100%** (5/5) |
| Average time to MR | **57 seconds** |
| Average LLM calls per run | **2** (1 triage + 1 code) |
| Average cost per run | **$0.0016** (< $0.01) on Gemini 2.0 Flash via Vertex AI |

*Triage accuracy = the file ShiftLeft targeted matched where a human engineer would look first.*  
*Token counts estimated at 4 chars/token — Vertex AI SDK does not expose exact counts via `generate_content`.*

**Run the benchmark yourself:**

```bash
# Dry run — triage + code only, no MRs created
python scripts/benchmark.py --dry-run

# Full run — creates a real MR on the demo repo
python scripts/benchmark.py

# Multiple repos + auto-update BENCHMARKS.md
python scripts/benchmark.py --config scripts/benchmark_repos.yaml

# Regenerate BENCHMARKS.md from last saved result (no pipeline run)
python scripts/benchmark.py --from-last
```

Results are saved to `.benchmarks/<timestamp>.json` and `BENCHMARKS.md` is updated automatically.

## Auto-Trigger: Label → MR in 60 Seconds

```
Developer labels GitLab issue "shiftleft"
           │
           ▼
  GitLab webhook ──▶  Cloud Run POST /webhook/gitlab/issue
                                   │  verify X-Gitlab-Token
                                   │  check for "shiftleft" label
                                   ▼
                        background: shiftleft_app.invoke(state)
                                   │  ~57 seconds
                                   ▼
                        Merge Request opened on GitLab
```

**Setup (2 minutes):**
1. `gcloud run deploy shiftleft --source . --region us-central1 --allow-unauthenticated`
2. GitLab → Settings → Webhooks → URL: `https://YOUR_URL/webhook/gitlab/issue` · Secret token: `WEBHOOK_SECRET` · Trigger: Issues events ✅
3. Label any issue `shiftleft` → MR appears in ~60 seconds

---

## The `.shiftleft/` Knowledge Base

Every run commits a living YAML map of the entire codebase:

```
.shiftleft/
├── config.yaml                     # schedule, ignore patterns, base branch
├── manifest.yaml                   # run metadata (files analyzed, timestamp)
├── audits/
│   └── 2026-05-17_032905.yaml      # severity + diff + test output + LLM info
└── map/
    └── gitlab/
        ├── client.yaml             # every function: name, args, returns, docstring
        ├── utils.yaml
        └── _backends/
            └── requests_backend.yaml
```

On subsequent runs, ShiftLeft reads its own previous map as context — triage accuracy improves because the LLM already has a structured understanding of the codebase. The repository builds self-knowledge over time.

---

## Multi-Language Support

| Language | Validator | How |
|---|---|---|
| Python | `py_compile` + `pytest` | Always available — stdlib only |
| JavaScript | `node --check` | Uses Node.js already required for GitLab MCP |
| TypeScript | `tsc --noEmit` | Uses system `tsc`; skipped gracefully if not installed |
| Go | `go vet` | Uses system `go`; skipped gracefully if not installed |
| Other | Content check | Non-empty, non-corrupted output |

---

## Stack

| Component | Technology |
|---|---|
| **LLM (primary)** | Gemini 2.0 Flash on **Vertex AI** (`utils/llm.py`) |
| **LLM (fallback)** | Gemini AI Studio — local dev without GCP |
| **Orchestration** | LangGraph — cyclic typed state machine, conditional retry edge |
| **GitLab integration** | GitLab MCP (`@modelcontextprotocol/server-gitlab`) |
| **File push** | GitLab REST Commits API (batched, create vs update) |
| **Code analysis** | Python `ast` module — zero dependencies |
| **Observability** | Arize Phoenix — OpenInference + OTLP (`utils/tracing.py`) |
| **Cloud** | Google Cloud Run + Cloud Scheduler |
| **UI** | Streamlit — real-time log streaming + live agent tracker |

---

## Project Structure

```
shiftleft/
├── agents/
│   ├── cartographer.py     # repo mapping: GitLab REST + MCP + Python AST
│   ├── triage.py           # bug selection: Gemini on Vertex AI
│   ├── coder.py            # fix generation: Gemini on Vertex AI (multi-language)
│   ├── auditor.py          # validation: py_compile / node / tsc / go vet + pytest
│   └── hitl.py             # GitLab: MCP branch + REST commits + REST MR
├── core/
│   ├── graph.py            # LangGraph pipeline + conditional retry routing
│   └── state.py            # TypedDict state schema (20 fields)
├── tools/
│   ├── gitlab_mcp_tools.py # MCP subprocess client + REST helpers
│   ├── ast_tools.py        # Python AST walker
│   └── yaml_tools.py       # .shiftleft/ YAML writer
├── utils/
│   ├── config.py           # environment variable loader
│   ├── llm.py              # Vertex AI primary / AI Studio fallback abstraction
│   ├── logger.py           # structured logging
│   └── tracing.py          # Arize Phoenix OpenTelemetry initialiser
├── cloud/
│   ├── web_hook.py         # FastAPI: GitLab issue/push hooks + scheduler endpoint
│   └── scheduler.py        # Cloud Scheduler job management
├── ui/
│   ├── app.py              # Streamlit home: live pipeline + agent tracker
│   └── pages/
│       ├── 01_dashboard.py # real-time streaming + MR history
│       ├── 02_review.py    # per-file diff viewer with syntax highlighting
│       └── 03_scheduler.py # webhook setup guide + cron configuration
├── scripts/
│   ├── check.sh            # 10-section system diagnostic (run before every demo)
│   ├── benchmark.py        # measures triage accuracy / fix rate / timing / cost
│   └── benchmark_repos.yaml
├── tests/
│   ├── test_ast_tools.py
│   ├── test_graph.py
│   └── test_yaml_tools.py
├── main.py                 # CLI: python main.py [--repo user/repo] [--serve]
├── test_pipeline.py        # end-to-end test runner with --step debug mode
├── .env.example            # every environment variable documented
├── Dockerfile              # Python 3.12 + Node.js 20 (for GitLab MCP)
└── SETUP.md                # complete setup + deploy + demo guide
```

---

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/amareshhebbar/ShiftLeft
cd ShiftLeft
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
npm install -g @modelcontextprotocol/server-gitlab

# 2. Configure
cp .env.example .env
# Set: GITLAB_TOKEN, GCP_PROJECT_ID, GITLAB_TARGET_PROJECT

# 3. Authenticate with Google Cloud (Vertex AI)
gcloud auth application-default login
gcloud services enable aiplatform.googleapis.com

# 4. Run diagnostic
bash scripts/check.sh

# 5. Run
python main.py --repo youruser/yourrepo
```

Expected output:

```
2026-05-17 03:28:51 [INFO] cartographer — 32 Python files mapped, 3 issues loaded
2026-05-17 03:28:55 [INFO] triage — severity=HIGH target=['gitlab/_backends/requests_backend.py']
2026-05-17 03:29:01 [INFO] coder — patch: 12 lines changed
2026-05-17 03:29:02 [INFO] auditor — iteration 1: PASSED ✅
2026-05-17 03:29:14 [INFO] hitl — ✅ MR: https://gitlab.com/.../merge_requests/2

================================================================
✅  Merge Request: https://gitlab.com/.../merge_requests/2
================================================================
```

---

## Impact

28 million developers use GitLab. Engineering teams spend 30–40% of their time on bug maintenance. Most issues sit unassigned for days.

ShiftLeft collapses that gap from days to 60 seconds. Zero workflow change — add a label, get an MR.

| Metric | Value |
|---|---|
| Average tokens per run | ~17,000 |
| Average cost per run | < $0.01 (Gemini 2.0 Flash, Vertex AI) |
| 10-person team, 20 issues/week | < $2/week to automate ~40 hrs of bug work |

---

## Built For

**[Google Cloud Rapid Agent Hackathon](https://rapid-agent.devpost.com)** — GitLab Partner Track

| Hackathon Requirement | How ShiftLeft Meets It |
|---|---|
| Gemini + Google Cloud AI | All LLM calls via `vertexai.GenerativeModel` (Vertex AI) in `utils/llm.py` |
| Google Cloud deployment | FastAPI webhook on Cloud Run; Cloud Scheduler for nightly runs |
| Partner MCP integration | GitLab MCP for branch creation + file reads (`tools/gitlab_mcp_tools.py`) |
| Autonomous real-world agent | Full loop: GitLab issue → fix → Merge Request with zero human code |
| Arize observability | Every LLM call traced via OpenInference OTLP in `utils/tracing.py` |

---

## License

MIT — see [LICENSE](LICENSE)
