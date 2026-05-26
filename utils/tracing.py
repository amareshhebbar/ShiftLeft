
from __future__ import annotations

import logging
import os

from utils.config import ARIZE_API_KEY, PHOENIX_ENDPOINT

log = logging.getLogger(__name__)

_initialized = False


def init_tracing() -> bool:
    """
    Initialize Arize Phoenix tracing.

    Returns True if tracing was activated, False if it was skipped
    (missing deps or config).  Never raises.
    """
    global _initialized
    if _initialized:
        return True

    try:
        from phoenix.otel import register  # arize-phoenix-otel
    except ImportError:
        log.info(
            "Arize tracing: SKIPPED (arize-phoenix-otel not installed — "
            "run: pip install arize-phoenix-otel)"
        )
        return False

    try:
        kwargs: dict = {"project_name": "shiftleft"}

        if ARIZE_API_KEY:
            kwargs["api_key"] = ARIZE_API_KEY
            kwargs["endpoint"] = "https://app.phoenix.arize.com/v1/traces"
            log.info("Arize Phoenix: connecting to Phoenix Cloud (app.phoenix.arize.com)")
        else:
            kwargs["endpoint"] = f"{PHOENIX_ENDPOINT}/v1/traces"
            log.info(f"Arize Phoenix: connecting to self-hosted Phoenix at {PHOENIX_ENDPOINT}")

        tracer_provider = register(**kwargs)

        # ── Instrument Vertex AI (primary LLM backend) ────────────────────
        try:
            from openinference.instrumentation.vertexai import VertexAIInstrumentor  # type: ignore
            VertexAIInstrumentor().instrument(tracer_provider=tracer_provider)
            log.info("Arize Phoenix: VertexAIInstrumentor ✅")
        except ImportError:
            log.debug("openinference-instrumentation-vertexai not installed — skipping Vertex spans")

        # ── Instrument google-generativeai (AI Studio fallback) ───────────
        try:
            from openinference.instrumentation.google_generativeai import (  # type: ignore
                GoogleGenerativeAIInstrumentor,
            )
            GoogleGenerativeAIInstrumentor().instrument(tracer_provider=tracer_provider)
            log.info("Arize Phoenix: GoogleGenerativeAIInstrumentor ✅")
        except ImportError:
            log.debug("openinference-instrumentation-google-generativeai not installed")

        # ── Instrument LangChain / LangGraph ─────────────────────────────
        try:
            from openinference.instrumentation.langchain import LangChainInstrumentor  # type: ignore
            LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
            log.info("Arize Phoenix: LangChainInstrumentor (LangGraph) ✅")
        except ImportError:
            log.debug("openinference-instrumentation-langchain not installed")

        _initialized = True
        log.info(
            "✅ Arize Phoenix tracing ACTIVE — all LLM calls will be traced. "
            "View at app.phoenix.arize.com (project: shiftleft)"
        )
        return True

    except Exception as exc:
        log.warning(f"Arize Phoenix tracing: DISABLED — {exc}")
        return False