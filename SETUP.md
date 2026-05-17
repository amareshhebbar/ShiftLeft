# ShiftLeft — Setup, Testing & Demo Guide

---

## Prerequisites

- Python 3.10+
- Node.js 18+ (`node --version` to check)
- GitLab account with a Personal Access Token
- Google Gemini API key (free at [aistudio.google.com](https://aistudio.google.com))

---

## 1. Install

```bash
git clone https://github.com/gvamaresh/shiftleft
cd shiftleft
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# GitLab MCP server (one-time)
npm install -g @modelcontextprotocol/server-gitlab
```

---

## 2. Configure `.env`

Create `.env` in the project root:

```dotenv
# Required
GEMINI_API_KEY="AIza..."
GEMINI_MODEL="gemini-3.1-pro"

GITLAB_TOKEN="glpat-..."
GITLAB_URL="https://gitlab.com"
GITLAB_TARGET_PROJECT="youruser/yourrepo"

# Optional — LangSmith tracing
LANGCHAIN_TRACING_V2="true"
LANGCHAIN_API_KEY="ls__..."
LANGCHAIN_PROJECT="shiftleft-dev"

# Optional — Cloud Run webhook
CLOUD_RUN_URL="https://your-cloud-run-url.run.app"
```

**GitLab token scopes needed** (create at `gitlab.com/-/user_settings/personal_access_tokens`):

| Scope              | Why                       |
| ------------------ | ------------------------- |
| `api`              | Full API + MCP access     |
| `read_repository`  | Read file contents        |
| `write_repository` | Push commits and branches |

---

---

## 3. Run the pipeline

### One command — full run

```bash
python main.py
```

Against a different repo:

```bash
python main.py --repo someuser/some-other-gitlab-repo
```

### Streamlit dashboard

```bash
streamlit run ui/app.py
# Opens http://localhost:8501
```

### Webhook server (Cloud Run mode)

```bash
python main.py --serve
# Listens on :8080
```

---

## 4. Testing with fake issues (demo setup)

Use `test_pipeline.py` — it never touches `main.py` and gives verbose step-by-step output.

### Step A — Create the 3 demo issues on GitLab

```bash
python test_pipeline.py --issues
```

This creates these 3 real issues on your `GITLAB_TARGET_PROJECT`:

```
#1 Missing error handling in http module when connection times out
#2 No retry logic for API rate limit responses (HTTP 429)
#3 gl.projects.list() does not handle pagination edge cases
```

These are real bugs in the python-gitlab library. Gemini consistently picks **Issue #2** (HTTP 429 retry) as the highest severity and targets `gitlab/_backends/requests_backend.py`.

### Step B — Run the full pipeline (issues already exist)

```bash
python test_pipeline.py --no-issues
```

Output you'll see:

```
STEP 0 — skipped (--no-issues)
STEP 1 — Cartographer: 32 files mapped, 3 issues loaded
STEP 2 — Triage: severity=HIGH, target=gitlab/_backends/requests_backend.py
STEP 3 — Coder: +12 lines added (retry logic with urllib3.Retry)
STEP 4 — Auditor: PASSED (syntax OK)
STEP 5 — HITL: branch created, 36 files committed, MR opened

MR URL: https://gitlab.com/youruser/yourrepo/-/merge_requests/N
```

### Step C — Debug individual agents

```bash
python test_pipeline.py --step carto    # stop after cartographer — see what files mapped
python test_pipeline.py --step triage   # stop after triage — see what Gemini picked
python test_pipeline.py --step coder    # stop after coder — see the full diff
python test_pipeline.py --step auditor  # stop after auditor — see syntax check result
# no --step flag = run all 5 agents through to MR creation
```

---

## 5. Pre-demo checklist (before recording video)

```bash
# 1. Delete old test branches
#    gitlab.com/youruser/yourrepo/-/branches
#    Delete all: shiftleft/run-*

# 2. Close old MRs
#    gitlab.com/youruser/yourrepo/-/merge_requests
#    Close MR #1 and any others

# 3. Confirm issues #1 #2 #3 are OPEN
#    gitlab.com/youruser/yourrepo/-/issues

# 4. Do one clean test run
python test_pipeline.py --no-issues

# 5. Verify MR appeared on GitLab — open the URL printed at the end

# 6. Clean up that run too (delete branch + close MR)

# Now record the real demo
```

---

## 6. What the demo shows

1. **GitLab issues tab** — 3 open bugs, nobody has fixed them
2. **Terminal** — `python main.py` — logs stream live
3. **Cartographer** — "32 Python files mapped via GitLab MCP"
4. **Triage** — "Gemini picked Issue #2, severity HIGH"
5. **Coder** — "Fix written — 12 lines added"
6. **Auditor** — "Syntax OK, tests passed"
7. **HITL** — "Branch created via MCP, MR opened"
8. **GitLab MR page** — real unified diff, Changes tab
9. **`.shiftleft/` folder** — 34 YAML files documenting the codebase
10. **Audit log** — `.shiftleft/audits/YYYY-MM-DD_HHMMSS.yaml`

---

## 7. Troubleshooting

| Error                               | Fix                                                                                              |
| ----------------------------------- | ------------------------------------------------------------------------------------------------ |
| `npx not found`                     | `sudo dnf install nodejs` or `sudo apt install nodejs npm`                                       |
| `GEMINI_MODEL looks wrong`          | Must be exactly `gemini-3.1-pro`                                                               |
| `GITLAB_TARGET_PROJECT looks wrong` | Must be `user/repo` — no `https://` prefix                                                       |
| `MCP handshake timed out`           | Run `GITLAB_PERSONAL_ACCESS_TOKEN=glpat-... npx -y @modelcontextprotocol/server-gitlab` manually |
| `GitLab commit 403`                 | Token needs `write_repository` scope                                                             |
| `FutureWarning google.generativeai` | Safe to ignore — package still works                                                             |
| Triage picks `docs/conf.py`         | You have an old `triage.py` — pull latest from repo                                              |
