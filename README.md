<div align="center">

# ShiftLeft

### Autonomous Bug-Fixing Agent for GitLab

*"Point it at any repo. It finds the bug, writes the fix, opens the MR."*

<br/>

[![Python](https://img.shields.io/badge/Built_with-Python_3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Gemini](https://img.shields.io/badge/LLM-Gemini_2.5_Flash-4285F4?style=for-the-badge&logo=googlegemini&logoColor=white)](https://deepmind.google/technologies/gemini/)
[![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-000000?style=for-the-badge&logo=chainlink&logoColor=white)](https://langchain-ai.github.io/langgraph/)
[![GitLab MCP](https://img.shields.io/badge/Integration-GitLab_MCP-FC6D26?style=for-the-badge&logo=gitlab&logoColor=white)](https://gitlab.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-22c55e?style=for-the-badge)](LICENSE)

<br/>

**ShiftLeft** is a 5-agent autonomous software engineering system.
It reads any GitLab repository, finds the highest-impact open bug using **Gemini 3.1 Pro**,
writes a targeted fix, validates it, and opens a Merge Request — without a human writing a single line of code.

<br/>

[**Watch Demo**](https://youtu.be/0qyFCHWVS6g) &nbsp;·&nbsp;
[**Live MR Example**](https://gitlab.com/amareshhebbar/python-gitlab-forktesting/-/merge_requests/2) &nbsp;·&nbsp;
[**Setup & Testing Guide**](SETUP.md)

</div>

---

## What It Does

```
You run:   python main.py

ShiftLeft:
  1. Reads every Python file in your GitLab repo (via GitLab MCP + REST)
  2. AST-parses each file → function signatures, classes, imports
  3. Fetches open GitLab issues
  4. Sends everything to Gemini 3.1 Pro → picks the highest-severity bug
  5. Gemini writes the complete fix
  6. Auditor validates syntax (self-correction loop: retries up to 3×)
  7. Creates a branch (via GitLab MCP)
  8. Pushes the fix + YAML knowledge-map files (via GitLab REST)
  9. Opens a Merge Request for human review

Total time: ~60 seconds
```

---

## Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     LangGraph State Machine                      │
│                                                                   │
│  ┌──────────────┐    ┌────────┐    ┌───────┐    ┌──────────┐   │
│  │ Cartographer │───▶│ Triage │───▶│ Coder │───▶│ Auditor  │   │
│  │              │    │        │    │       │    │          │   │
│  │ • REST tree  │    │ Gemini │    │ Gemini│    │ syntax   │   │
│  │ • MCP files  │    │ picks  │    │ writes│    │ check    │   │
│  │ • MCP issues │    │ bug    │    │ fix   │    │ pytest   │   │
│  │ • AST parse  │    │        │    │       │    │          │   │
│  │ • YAML docs  │    │        │    │       │    └────┬─────┘   │
│  └──────────────┘    └────────┘    └───────┘         │         │
│                                         ▲        pass │ fail   │
│                                         └─────────────┘         │
│                                           (max 3 retries)        │
│                                                   │ pass         │
│                                            ┌──────▼──────┐      │
│                                            │     HITL    │      │
│                                            │ MCP: branch │      │
│                                            │ REST: commit│      │
│                                            │ REST: MR    │      │
│                                            └─────────────┘      │
└─────────────────────────────────────────────────────────────────┘
```

### Agent Responsibilities

| Agent | Tool | What it does |
|---|---|---|
| **Cartographer** | GitLab REST + MCP | Maps repo tree, reads files, fetches open issues, builds YAML docs |
| **Triage** | Gemini 3.1 Pro | Reads file map + issues, selects highest-severity bug |
| **Coder** | Gemini 3.1 Pro | Reads target file, generates complete fixed version + unified diff |
| **Auditor** | py_compile + pytest | Validates syntax, runs tests, triggers self-correction on failure |
| **HITL** | GitLab MCP + REST | Creates branch (MCP), commits files (REST), opens MR (REST) |

---

## The `.shiftleft/` Knowledge Base

Every run commits a YAML knowledge map to the target repo:

```
.shiftleft/
├── config.yaml                    # schedule, ignore list, base branch
├── manifest.yaml                  # run metadata
├── audits/
│   └── 2026-05-17_032905.yaml     # full audit log per run
└── map/
    └── gitlab/
        ├── client.yaml            # every function: args, returns, docstring
        ├── utils.yaml
        └── _backends/
            └── requests_backend.yaml
```

This improves with every run — the repo builds a machine-readable understanding of itself over time.

---

## Stack

| Component | Technology |
|---|---|
| LLM | Gemini 3.1 Pro (1M token context) |
| Orchestration | LangGraph (cyclic state machine with conditional retry edge) |
| GitLab integration | GitLab MCP (`@modelcontextprotocol/server-gitlab`) |
| File discovery | GitLab REST API |
| Code analysis | Python `ast` module |
| Language | Python 3.10+ |
| Cloud | Google Cloud Run + Cloud Scheduler |
| UI | Streamlit |

---

## Project Structure

```
shiftleft/
├── agents/
│   ├── cartographer.py     # repo mapping via GitLab MCP + REST
│   ├── triage.py           # bug selection via Gemini
│   ├── coder.py            # fix generation via Gemini
│   ├── auditor.py          # syntax check + pytest sandbox
│   └── hitl.py             # branch + commit + MR via GitLab
├── core/
│   ├── graph.py            # LangGraph pipeline wiring
│   └── state.py            # TypedDict state schema (20 fields)
├── tools/
│   ├── gitlab_mcp_tools.py # MCP subprocess client + REST helpers
│   ├── ast_tools.py        # Python AST walker
│   └── yaml_tools.py       # .shiftleft/ YAML writer
├── cloud/
│   ├── web_hook.py         # FastAPI webhook (Cloud Run)
│   └── scheduler.py        # Cloud Scheduler wrapper
├── ui/
│   ├── app.py              # Streamlit entry point
│   └── pages/
│       ├── 01_dashboard.py # run history + manual trigger
│       ├── 02_review.py    # per-file diff viewer
│       └── 03_scheduler.py # cron config
├── utils/
│   ├── config.py           # env var loader
│   └── logger.py           # structured logging
├── main.py                 # CLI entry point
├── test_pipeline.py        # full e2e test runner
└── SETUP.md                # complete setup + testing guide
```

---

## Live Demo

ShiftLeft fixed a real bug in [python-gitlab](https://gitlab.com/amareshhebbar/python-gitlab-forktesting):

- **Issue #2:** "No retry logic for API rate limit responses (HTTP 429)"
- **Fix:** Added `urllib3.Retry` with `status_forcelist=[429]` and exponential backoff to `RequestsBackend`
- **MR:** [!2 — fix(high): Missing retry logic for HTTP 429](https://gitlab.com/amareshhebbar/python-gitlab-forktesting/-/merge_requests/2)
- **Time:** 60 seconds from trigger to open MR

---

## Built for

**Google Cloud Rapid Agent Hackathon** — GitLab Partner Track

Targeting 28 million GitLab developers who spend 40% of their time on bug backlog that never gets resolved.

→ **[Full setup, testing, and demo guide](SETUP.md)**

---

## License

MIT — see [LICENSE](LICENSE)