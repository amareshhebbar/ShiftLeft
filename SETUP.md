# ShiftLeft — Developer Setup & Testing Guide

## Full `.env` reference

```dotenv
# ── Gemini ──────────────────────────────────────────────────
GEMINI_API_KEY="AIzaSy..."
GEMINI_MODEL="gemini-2.5-flash"          # must be exactly this string

# ── GitLab ──────────────────────────────────────────────────
GITLAB_TOKEN="glpat-..."                 # needs: api, read_repository, write_repository
GITLAB_URL="https://gitlab.com"
GITLAB_MCP_URL="https://gitlab.com/api/v4/mcp"   # not used currently (npm fallback)
GITLAB_TARGET_PROJECT="youruser/yourrepo"         # NO https://, just the path

# ── Google Cloud (optional — for Cloud Run / Scheduler) ─────
GCP_PROJECT_ID="shiftleft-hackathon-xxxxx"
GCP_REGION="us-central1"
GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"

# ── Webhook (optional — for Cloud Run mode) ─────────────────
WEBHOOK_SECRET="some-random-secret"
CLOUD_RUN_URL="https://your-cloud-run-url.run.app"

# ── LangSmith tracing (optional) ────────────────────────────
LANGCHAIN_TRACING_V2="true"
LANGCHAIN_API_KEY="ls__..."
LANGCHAIN_PROJECT="shiftleft-dev"
```

---

## One-time setup

```bash
# 1. Clone
git clone https://github.com/gvamaresh/shiftleft
cd shiftleft

# 2. Python env
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Node (for GitLab MCP server)
npm install -g @modelcontextprotocol/server-gitlab

# 4. Copy and fill .env
cp .env.example .env
nano .env   # fill in GEMINI_API_KEY and GITLAB_TOKEN at minimum

# 5. Verify everything
python diagnose.py
# Must show: ALL CHECKS PASSED ✅
```

---

## Running the pipeline

### Option A — Quick full run (recommended for demo)

```bash
python main.py
```

What happens:
1. Reads your `GITLAB_TARGET_PROJECT` from `.env`
2. Maps the repo (30-45s depending on size)
3. Triages bugs with Gemini (~5s)
4. Generates fix (~10s)
5. Validates syntax (~1s)
6. Creates branch + commits + opens MR (~10s)
7. Prints the MR URL

### Option B — Test runner with demo issues

```bash
# Full run — creates 3 demo issues first, then runs all 5 agents
python test_pipeline.py

# Only create the 3 demo issues (run this before recording video)
python test_pipeline.py --issues

# Run pipeline without creating issues (issues already exist)
python test_pipeline.py --no-issues

# Debug individual agents:
python test_pipeline.py --step carto    # stop after cartographer
python test_pipeline.py --step triage   # stop after triage (see what Gemini picked)
python test_pipeline.py --step coder    # stop after coder (see the diff)
python test_pipeline.py --step auditor  # stop after auditor (see test results)
```

### Option C — Against a different repo

```bash
python main.py --repo someuser/some-other-gitlab-repo
```

### Option D — Streamlit dashboard

```bash
streamlit run ui/app.py
# Opens http://localhost:8501
```

### Option E — Webhook server (Cloud Run)

```bash
python main.py --serve
# Listens on :8080 for GitLab webhook events
```

---

## Pre-demo checklist (before recording video)

```bash
# 1. Delete old test branches from GitLab
#    gitlab.com/youruser/yourrepo/-/branches
#    Delete all shiftleft/run-* branches

# 2. Close any old MRs
#    gitlab.com/youruser/yourrepo/-/merge_requests

# 3. Make sure issues #1 #2 #3 are OPEN
#    gitlab.com/youruser/yourrepo/-/issues

# 4. Verify pipeline still works
python test_pipeline.py --no-issues

# 5. Check MR appeared on GitLab
#    Open the URL that printed at the end

# 6. Clean up that test run too (delete branch + close MR)
#    Then you're ready to record the real demo
```

---

## What the demo issues are

ShiftLeft creates these 3 issues automatically on first run:

```
#1 Missing error handling in http module when connection times out
#2 No retry logic for API rate limit responses (HTTP 429)
#3 gl.projects.list() does not handle pagination edge cases
```

These are real bugs in the python-gitlab library. Gemini consistently picks
issue #2 (HTTP 429 retry) as highest severity and targets `requests_backend.py`.

---

## How the MCP integration works

The GitLab MCP server (`@modelcontextprotocol/server-gitlab`) is launched as a
subprocess using JSON-RPC over stdio. ShiftLeft uses it for:

| Operation | Transport | Why |
|---|---|---|
| `create_branch` | MCP | Works reliably |
| `list_available_tools` | MCP | Handshake / discovery |
| `get_file_contents` | MCP → REST fallback | MCP 404s on some paths |
| `list_issues` | REST | Not exposed by npm package |
| `get_repository_tree` | REST | Not exposed by npm package |
| `push files / commit` | REST | MCP has JS bug (`.map()` on undefined) |
| `create_merge_request` | REST | More reliable than MCP |

All write operations that matter for the demo story go through the MCP layer
(branch creation). File commits use the GitLab Commits REST API.

---

## Troubleshooting

| Error | Fix |
|---|---|
| `npx not found` | Install Node.js: `sudo dnf install nodejs` |
| `MCP handshake timed out` | Run `npx -y @modelcontextprotocol/server-gitlab` manually to see error |
| `GEMINI_MODEL looks wrong` | Must be exactly `gemini-2.5-flash` in `.env` |
| `GITLAB_TARGET_PROJECT looks wrong` | Must be `user/repo` not `https://gitlab.com/user/repo` |
| `GitLab commit 403` | Token needs `write_repository` scope |
| `FutureWarning google.generativeai` | Safe to ignore — package still works |
| Triage picks `docs/conf.py` | Outdated triage.py — copy latest from repo |

---

## File purposes

```
main.py              CLI entry — runs pipeline via LangGraph graph
test_pipeline.py     Safe e2e test — same pipeline, verbose output, --step debug
diagnose.py          Pre-flight checks (env, imports, MCP, Gemini, state, agents)
agents/cartographer  Maps repo: REST tree + MCP file reads + REST issues + YAML docs
agents/triage        Gemini picks highest-severity bug from file map + issues
agents/coder         Gemini writes complete fixed file + computes unified diff  
agents/auditor       py_compile syntax check + optional pytest run
agents/hitl          MCP branch + REST commit batches + REST MR creation
core/graph           LangGraph wiring: 5 nodes + conditional retry edge
core/state           TypedDict schema for all 20 state fields
tools/gitlab_mcp_tools   Subprocess MCP client + REST helpers (tree, issues, file)
```