import os
from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    val = os.getenv(key, "").strip()
    if not val:
        raise EnvironmentError(
            f"Required env var '{key}' is not set. "
            f"Add it to your .env file."
        )
    return val

def _optional(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


# ── Google Cloud / Vertex AI ─────────────────────────────────────────────────
GCP_PROJECT_ID = _optional("GCP_PROJECT_ID", "")
GCP_REGION     = _optional("GCP_REGION", "us-central1")
GEMINI_MODEL   = _optional("GEMINI_MODEL", "gemini-3.1-pro")

# AI Studio key — fallback only when GCP_PROJECT_ID is absent
GEMINI_API_KEY = _optional("GEMINI_API_KEY", "")

# ── GitLab ───────────────────────────────────────────────────────────────────
GITLAB_TOKEN          = _require("GITLAB_TOKEN")
GITLAB_URL            = _optional("GITLAB_URL", "https://gitlab.com")
GITLAB_TARGET_PROJECT = _optional("GITLAB_TARGET_PROJECT", "")

# ── Arize Phoenix (observability — enables Arize prize track) ─────────────────
ARIZE_API_KEY    = _optional("ARIZE_API_KEY", "")
PHOENIX_ENDPOINT = _optional("PHOENIX_ENDPOINT", "https://app.phoenix.arize.com")

# ── Cloud Run / Webhook ──────────────────────────────────────────────────────
WEBHOOK_SECRET = _optional("WEBHOOK_SECRET", "change-me-in-production")
CLOUD_RUN_URL  = _optional("CLOUD_RUN_URL", "http://localhost:8080")