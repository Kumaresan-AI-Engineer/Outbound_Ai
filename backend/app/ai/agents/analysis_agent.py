"""Post-call reporting agent: transcript analysis + weekly performance summary."""

import logging

from app.ai.prompts.analysis_prompts import build_analysis_messages, build_weekly_summary_messages
from app.ai.providers.factory import get_provider
from app.ai.schemas.analysis import CallAnalysis, WeeklySummary
from app.config import get_settings

logger = logging.getLogger(__name__)


def _model_for(provider) -> str:
    settings = get_settings()
    return settings.groq_model if provider.name == "groq" else settings.openai_model


async def analyze_call(transcript: str, contact_name: str = "", provider_name: str | None = None) -> dict:
    """Generate post-call analysis from the complete transcript."""
    provider = get_provider(provider_name)
    messages = build_analysis_messages(transcript, contact_name)
    try:
        result = await provider.complete_structured(
            messages, CallAnalysis, model=_model_for(provider), temperature=0.3, max_tokens=1000
        )
        return result.model_dump()
    except Exception as e:
        logger.error(f"[ANALYSIS] Failed: {e}")
        return {"error": str(e), "summary": "Analysis failed."}


async def generate_weekly_summary(digest: str, call_count: int, provider_name: str | None = None) -> dict:
    """Generate an AI-powered weekly summary of call performance."""
    provider = get_provider(provider_name)
    messages = build_weekly_summary_messages(digest, call_count)
    try:
        result = await provider.complete_structured(
            messages, WeeklySummary, model=_model_for(provider), temperature=0.4, max_tokens=600
        )
        return result.model_dump()
    except Exception as e:
        logger.error(f"[WEEKLY SUMMARY] Failed: {e}")
        return {"error": str(e), "headline": "Weekly summary unavailable."}
