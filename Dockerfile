# ── Stage 1: Python + Node.js combined image ──────────────────────────────────
FROM python:3.12-slim

# System deps + Node.js 20 (required for @modelcontextprotocol/server-gitlab)
RUN apt-get update && apt-get install -y \
        git curl ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Verify Node.js version
RUN node --version && npm --version

# Install GitLab MCP server globally (required by tools/gitlab_mcp_tools.py)
RUN npm install -g @modelcontextprotocol/server-gitlab

WORKDIR /app

# Install Python dependencies first (layer-cache friendly)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Cloud Run listens on PORT env var (default 8080)
EXPOSE 8080

# ── Environment variable documentation ────────────────────────────────────────
# Required at runtime:
#   GITLAB_TOKEN             — GitLab PAT (api, read_repository, write_repository)
#   GCP_PROJECT_ID           — Google Cloud project (for Vertex AI)
#
# Optional:
#   GCP_REGION               — Vertex AI region (default: us-central1)
#   GEMINI_MODEL             — model ID (default: gemini-3.1-pro)
#   GITLAB_TARGET_PROJECT    — default repo (user/repo)
#   GITLAB_URL               — GitLab host (default: https://gitlab.com)
#   WEBHOOK_SECRET           — GitLab webhook token
#   ARIZE_API_KEY            — Arize Phoenix Cloud key (for observability)
#
# Vertex AI authentication in Cloud Run:
#   Attach a service account with roles/aiplatform.user — no API key needed.
#   Locally: run `gcloud auth application-default login` before starting.

CMD ["python", "main.py", "--serve"]