"""
Central config — all env vars read once at import time.
Import from here; never call os.getenv() in agent files.
"""

import os
from dotenv import load_dotenv

load_dotenv()

def _require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise EnvironmentError(
            f"Required env var '{key}' is not set. "
            f"Check your .env file against .env.example."
        )
    return val

# ── Gemini ─────────────────────────────────────────────────────────────────
GEMINI_API_KEY  = _require("GEMINI_API_KEY")
GEMINI_MODEL    = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-lite")

# ── GitHub ─────────────────────────────────────────────────────────────────
GITHUB_TOKEN        = _require("GITHUB_TOKEN")
GITHUB_TARGET_REPO  = os.getenv("GITHUB_TARGET_REPO", "")
DEFAULT_BASE_BRANCH = os.getenv("DEFAULT_BASE_BRANCH", "main")

# ── GCP ────────────────────────────────────────────────────────────────────
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")
GCP_REGION     = os.getenv("GCP_REGION", "us-central1")

# ── App ────────────────────────────────────────────────────────────────────
WEBHOOK_SECRET  = os.getenv("WEBHOOK_SECRET", "change-me-in-production")
CLOUD_RUN_URL   = os.getenv("CLOUD_RUN_URL", "http://localhost:8080")
SEARXNG_URL     = os.getenv("SEARXNG_URL", "http://localhost:8080")