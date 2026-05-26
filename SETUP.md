# ShiftLeft — Setup, Testing & Demo Guide

## Stack

| Component | Technology |
|---|---|
| LLM (primary) | **Gemini 2.0 Flash on Vertex AI** (`utils/llm.py`) |
| LLM (fallback) | Gemini AI Studio — local dev when GCP not configured |
| Orchestration | LangGraph — cyclic 5-agent state machine |
| GitLab integration | GitLab MCP (`@modelcontextprotocol/server-gitlab`) |
| Observability | **Arize Phoenix** (OpenInference + OTLP via `utils/tracing.py`) |
| Cloud | Google Cloud Run + Cloud Scheduler |
| UI | Streamlit — real-time streaming dashboard |

---

## Prerequisites

| Tool | Version | Check |
|---|---|---|
| Python | 3.10+ | `python3 --version` |
| Node.js | 18+ | `node --version` |
| npm / npx | any | `npx --version` |
| Google Cloud SDK | any | `gcloud --version` |
| GitLab account + PAT | — | gitlab.com/-/user_settings/personal_access_tokens |

---

## 1. Install

```bash
git clone https://github.com/amareshhebbar/ShiftLeft
cd ShiftLeft
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# GitLab MCP server (required — enables MCP tool calls)
npm install -g @modelcontextprotocol/server-gitlab
```

---

## 2. Configure `.env`

```bash
cp .env.example .env
# Open .env and fill in your values
```

**Minimum required:**

```env
GITLAB_TOKEN="glpat-xxxxxxxxxxxxxxxxxxxx"
GCP_PROJECT_ID="your-gcp-project-id"
GITLAB_TARGET_PROJECT="youruser/yourrepo"
```

### GitLab token scopes

Create at `gitlab.com/-/user_settings/personal_access_tokens`:

| Scope | Required for |
|---|---|
| `api` | Full API access + GitLab MCP |
| `read_repository` | File content reads |
| `write_repository` | Push commits and branches |

### Gemini model options (set in `.env`)

```env
GEMINI_MODEL="gemini-3.1-pro"   # default — fast, cheap, excellent
# GEMINI_MODEL="gemini-1.5-pro-002"   # heavier, more accurate triage
```

---

## 3. Vertex AI authentication

### Local development

```bash
gcloud auth application-default login
gcloud config set project your-gcp-project-id
gcloud services enable aiplatform.googleapis.com
```

No API key needed. The SDK uses Application Default Credentials automatically.

### Cloud Run (production)

Attach a service account with `roles/aiplatform.user`:

```bash
# Create the service account
gcloud iam service-accounts create shiftleft \
  --display-name "ShiftLeft"

# Grant Vertex AI inference role
gcloud projects add-iam-policy-binding YOUR_PROJECT \
  --member="serviceAccount:shiftleft@YOUR_PROJECT.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"

# Use it on Cloud Run
gcloud run deploy shiftleft \
  --service-account shiftleft@YOUR_PROJECT.iam.gserviceaccount.com ...
```

### Fallback: AI Studio (no GCP)

If `GCP_PROJECT_ID` is not set, ShiftLeft automatically falls back to AI Studio:

```env
GEMINI_API_KEY="AIza..."   # from aistudio.google.com (free)
```

This works for local testing but does NOT satisfy the hackathon Google Cloud requirement for production.

---

## 4. Run the pipeline

```bash
# Full pipeline run against your configured project
python main.py

# Run against a specific repo (overrides .env)
python main.py --repo youruser/yourrepo

# Streamlit UI (live streaming dashboard)
streamlit run ui/app.py

# Webhook server mode (Cloud Run)
python main.py --serve
```

### Expected terminal output

```
2026-05-17 03:28:51 [INFO] utils.llm — LLM backend: Vertex AI  project=my-gcp-project  region=us-central1  model=gemini-3.1-pro
2026-05-17 03:28:51 [INFO] cartographer — run_id=2026-05-17_032851  project=youruser/yourrepo
2026-05-17 03:28:52 [INFO] cartographer — fetching repository tree via GitLab REST API
2026-05-17 03:28:54 [INFO] cartographer — 32 Python files selected
2026-05-17 03:29:02 [INFO] cartographer — 32 YAML manifests built
2026-05-17 03:29:03 [INFO] cartographer — 3 open issues loaded
2026-05-17 03:29:03 [INFO] triage — 32 code files + 3 issues → Gemini (Vertex AI)
2026-05-17 03:29:07 [INFO] triage — severity=HIGH  target=['gitlab/_backends/requests_backend.py']
2026-05-17 03:29:07 [INFO] coder — iteration 1, targets: ['gitlab/_backends/requests_backend.py']
2026-05-17 03:29:07 [INFO] coder — calling Gemini (Vertex AI) for gitlab/_backends/requests_backend.py
2026-05-17 03:29:13 [INFO] coder — patch: 12 lines changed
2026-05-17 03:29:13 [INFO] auditor — iteration 1: PASSED ✅
2026-05-17 03:29:14 [INFO] hitl — ✅ branch created via GitLab MCP
2026-05-17 03:29:22 [INFO] hitl — committed batch 1 (12 files) via REST
2026-05-17 03:29:28 [INFO] hitl — committed batch 2 (36 manifests) via REST
2026-05-17 03:29:30 [INFO] hitl — ✅ MR: https://gitlab.com/youruser/yourrepo/-/merge_requests/3

================================================================
✅  Merge Request: https://gitlab.com/youruser/yourrepo/-/merge_requests/3
================================================================
```

---

## 5. Run the diagnostic check

Always run this before a demo:

```bash
bash scripts/check.sh          # full 10-section check
bash scripts/check.sh --fast   # skip network/API calls (~3 seconds)
bash scripts/check.sh --fix    # auto-install missing deps
```

Checks: Python version · Node.js · npx · GitLab MCP server · pip packages · env vars · GCP auth · Vertex AI SDK · GitLab token + scopes · target project access · MCP handshake · all .py syntax · all imports · Streamlit pages · Docker/gcloud.

---

## 6. Run benchmarks

```bash
# Against the default demo repo (creates a real MR)
python scripts/benchmark.py

# Dry run — triage + code only, no MR created
python scripts/benchmark.py --dry-run

# Single repo
python scripts/benchmark.py --repo youruser/yourrepo

# Multiple repos + write markdown output
python scripts/benchmark.py --config scripts/benchmark_repos.yaml --output BENCHMARKS.md
```

Results saved to `.benchmarks/<timestamp>.json`. The `--output` flag generates a formatted markdown table you can paste directly into your Devpost submission.

---

## 7. Arize Phoenix observability

### Option A: Arize Phoenix Cloud (recommended)

```bash
# 1. Get a free API key at app.phoenix.arize.com
# 2. Add to .env:
ARIZE_API_KEY="your-key-here"
```

Run ShiftLeft — every LLM call streams as OpenInference traces to Phoenix automatically.

### Option B: Self-hosted Phoenix

```bash
pip install arize-phoenix
python -m phoenix.server.main &    # starts on localhost:6006

# Add to .env:
PHOENIX_ENDPOINT="http://localhost:6006"
```

### What gets traced

- Every `utils.llm.generate()` call (triage + coder)
- Input tokens, output tokens, latency per call
- Every LangGraph node transition (cartographer → triage → coder → auditor → hitl)
- Retry loops with iteration count

---

## 8. GitLab webhook auto-trigger

### Deploy to Cloud Run

```bash
gcloud run deploy shiftleft \
  --source . \
  --region us-central1 \
  --service-account shiftleft@PROJECT.iam.gserviceaccount.com \
  --set-env-vars "GITLAB_TOKEN=glpat-...,GCP_PROJECT_ID=...,GITLAB_TARGET_PROJECT=user/repo,WEBHOOK_SECRET=your-secret" \
  --allow-unauthenticated
```

### Configure the GitLab webhook

Go to your GitLab project → **Settings → Webhooks → Add new webhook**:

```
URL:           https://YOUR_CLOUD_RUN_URL/webhook/gitlab/issue
Secret token:  (value of WEBHOOK_SECRET in .env)
Trigger:       ✅ Issues events
SSL:           ✅ Enable SSL verification
```

### Trigger a run

Open any issue in the GitLab project and add the label **`shiftleft`**. ShiftLeft fires within seconds, runs the full pipeline, and opens an MR in ~60 seconds.

---

## 9. Step-by-step debug mode

```bash
python test_pipeline.py --step carto     # run Cartographer only
python test_pipeline.py --step triage    # run through Triage
python test_pipeline.py --step coder     # run through Coder
python test_pipeline.py --step auditor   # run through Auditor
python test_pipeline.py --no-issues      # skip issue creation, full pipeline
```

---

## 10. Troubleshooting

| Error | Fix |
|---|---|
| `google.auth.exceptions.DefaultCredentialsError` | `gcloud auth application-default login` |
| `npx not found` | Install Node.js 18+ from nodejs.org |
| `GITLAB_TOKEN not set` | Add to `.env` and run `source .env` |
| `GitLab commit API 403` | Token needs `write_repository` scope |
| `MCP handshake timed out` | Run manually: `GITLAB_PERSONAL_ACCESS_TOKEN=$GITLAB_TOKEN npx -y @modelcontextprotocol/server-gitlab` |
| `Arize tracing SKIPPED` | `pip install arize-phoenix-otel openinference-instrumentation-vertexai openinference-instrumentation-langchain` |
| `vertexai.init failed` | `gcloud services enable aiplatform.googleapis.com --project=$GCP_PROJECT_ID` |
| LLM using AI Studio not Vertex AI | Set `GCP_PROJECT_ID` in `.env` and re-run |
| MR diff shows no changes | Coder returned same file — check `auditor` logs for retry context |

---

## 11. Pre-submission checklist

```bash
# 1. Full diagnostic
bash scripts/check.sh

# 2. Live pipeline test (creates a real MR)
python main.py --repo youruser/yourrepo

# 3. Benchmark run
python scripts/benchmark.py --dry-run --output BENCHMARKS.md

# 4. Confirm Streamlit is live
open https://shiftleft.streamlit.app

# 5. Confirm demo video is live and ≤3 min
open https://youtu.be/0qyFCHWVS6g

# 6. Confirm README on GitHub shows Vertex AI badge (not "Gemini 3.1 Pro")
open https://github.com/amareshhebbar/ShiftLeft

# 7. Submit on Devpost:
#    Hosted URL:  https://shiftleft.streamlit.app
#    Code repo:   https://github.com/amareshhebbar/ShiftLeft
#    Demo video:  https://youtu.be/0qyFCHWVS6g
#    Track:       GitLab (primary)
```