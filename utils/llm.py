from __future__ import annotations
import logging
from typing import Optional

from utils.config import GCP_PROJECT_ID, GCP_REGION, GEMINI_MODEL, GEMINI_API_KEY

log = logging.getLogger(__name__)

# ── Backend selection ─────────────────────────────────────────────────────────
USE_VERTEX = bool(GCP_PROJECT_ID)

if USE_VERTEX:
    try:
        import vertexai
        from vertexai.generative_models import GenerativeModel, GenerationConfig
        vertexai.init(project=GCP_PROJECT_ID, location=GCP_REGION)
        log.info(
            f"LLM backend: Vertex AI  "
            f"project={GCP_PROJECT_ID}  region={GCP_REGION}  model={GEMINI_MODEL}"
        )
    except ImportError as exc:
        log.warning(f"Vertex AI SDK not installed ({exc}); falling back to AI Studio.")
        USE_VERTEX = False

if not USE_VERTEX:
    if not GEMINI_API_KEY:
        raise EnvironmentError(
            "Set GCP_PROJECT_ID (for Vertex AI) or GEMINI_API_KEY (AI Studio fallback). "
            "Neither is configured."
        )
    import google.generativeai as _genai
    _genai.configure(api_key=GEMINI_API_KEY)
    log.warning(
        f"LLM backend: AI Studio (fallback)  model={GEMINI_MODEL}  "
        f"Set GCP_PROJECT_ID to use Vertex AI instead."
    )


# ── Public API ────────────────────────────────────────────────────────────────

def generate(
    prompt: str,
    temperature: float = 0.1,
    max_tokens: int = 16_384,
    model_override: Optional[str] = None,
) -> str:
    """
    Send a prompt to the configured Gemini model and return the text response.

    Args:
        prompt:         The complete prompt string.
        temperature:    Sampling temperature (0.0 = deterministic).
        max_tokens:     Maximum output tokens.
        model_override: Override the default model for this call only.

    Returns:
        Raw text from the model.

    Raises:
        RuntimeError: If the LLM call fails after retries.
    """
    model_id = model_override or GEMINI_MODEL

    if USE_VERTEX:
        model = GenerativeModel(model_id)
        try:
            response = model.generate_content(
                prompt,
                generation_config=GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                ),
            )
            return response.text
        except Exception as exc:
            log.error(f"Vertex AI generate failed (model={model_id}): {exc}")
            raise RuntimeError(f"Vertex AI LLM call failed: {exc}") from exc
    else:
        model = _genai.GenerativeModel(model_id)
        try:
            response = model.generate_content(
                prompt,
                generation_config=_genai.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                ),
            )
            return response.text
        except Exception as exc:
            log.error(f"AI Studio generate failed (model={model_id}): {exc}")
            raise RuntimeError(f"AI Studio LLM call failed: {exc}") from exc


def backend_info() -> dict:
    """Return a dict describing the active LLM backend (for UI display)."""
    if USE_VERTEX:
        return {
            "backend": "Vertex AI",
            "project": GCP_PROJECT_ID,
            "region":  GCP_REGION,
            "model":   GEMINI_MODEL,
        }
    return {
        "backend": "AI Studio (fallback)",
        "project": "N/A",
        "region":  "N/A",
        "model":   GEMINI_MODEL,
    }