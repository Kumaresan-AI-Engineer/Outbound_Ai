from openai import AsyncOpenAI
from groq import AsyncGroq
from app.config import get_settings

settings = get_settings()

_openai_client = None
_groq_client = None


def _get_openai():
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _openai_client


def _get_groq():
    global _groq_client
    if _groq_client is None:
        _groq_client = AsyncGroq(api_key=settings.groq_api_key)
    return _groq_client

SYSTEM_PROMPT = """You are an AI assistant helping a Business Analyst during a live outbound call.
Based on the conversation transcript, provide:
1. **Next Talking Point**: What the BA should say or ask next
2. **Objection Handling**: If the prospect raises concerns, suggest how to address them
3. **Sentiment**: Current prospect sentiment (Positive / Neutral / Negative)
4. **Key Insight**: Any important information mentioned by the prospect

Keep suggestions concise and actionable. Respond in JSON format:
{
  "next_talking_point": "...",
  "objection_handling": "...",
  "sentiment": "...",
  "key_insight": "..."
}"""


ANALYSIS_PROMPT = """You are an expert call analyst. Analyze this completed call transcript between a Business Agent and a prospect/customer.

Return a JSON object with exactly these fields:
{
  "summary": "2-3 sentence summary of what happened in the call",
  "sentiment": "Positive" or "Neutral" or "Negative",
  "quality_score": number from 1 to 10,
  "went_well": ["things the agent did well"],
  "to_improve": ["areas where the agent could improve"],
  "action_items": ["specific follow-up actions needed"],
  "follow_up_needed": true or false,
  "follow_up_reason": "why follow-up is needed (empty string if not needed)",
  "follow_up_date_suggestion": "suggested timeframe like 'in 2 days' or 'next week' (empty string if not needed)",
  "key_points": ["key topics and points discussed in the call"]
}

Be specific and actionable. Base everything on what was actually said in the transcript."""


async def analyze_call(transcript: str, provider: str = None) -> dict:
    """Generate post-call analysis from the complete transcript."""
    provider = provider or settings.ai_provider

    messages = [
        {"role": "system", "content": ANALYSIS_PROMPT},
        {"role": "user", "content": f"Call transcript:\n\n{transcript}\n\nAnalyze this call:"},
    ]

    try:
        if provider == "groq":
            response = await _get_groq().chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                temperature=0.3,
                max_tokens=1000,
                response_format={"type": "json_object"},
            )
        else:
            response = await _get_openai().chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.3,
                max_tokens=1000,
                response_format={"type": "json_object"},
            )

        import json
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"[ANALYSIS] Failed: {e}")
        return {"error": str(e), "summary": "Analysis failed."}


async def generate_weekly_summary(digest: str, call_count: int, provider: str = None) -> dict:
    """Generate an AI-powered weekly summary of call performance."""
    provider = provider or settings.ai_provider

    prompt = f"""You are an expert sales coach. Below is a digest of {call_count} outbound calls made this week.

{digest}

Return a JSON object with:
{{
  "headline": "one punchy sentence summarising the week",
  "wins": ["up to 3 things that went well across all calls"],
  "areas_to_improve": ["up to 3 coaching points"],
  "top_priority_action": "the single most important action for next week",
  "outlook": "Positive" or "Neutral" or "Needs Attention"
}}"""

    messages = [{"role": "user", "content": prompt}]

    try:
        if provider == "groq":
            response = await _get_groq().chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                temperature=0.4,
                max_tokens=600,
                response_format={"type": "json_object"},
            )
        else:
            response = await _get_openai().chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.4,
                max_tokens=600,
                response_format={"type": "json_object"},
            )

        import json
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"[WEEKLY SUMMARY] Failed: {e}")
        return {"error": str(e), "headline": "Weekly summary unavailable."}


async def get_suggestion(transcript: str, provider: str = None) -> dict:
    """Get AI-powered suggestion based on current transcript."""
    provider = provider or settings.ai_provider

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Current call transcript:\n\n{transcript}\n\nProvide suggestions:"},
    ]

    try:
        if provider == "groq":
            response = await _get_groq().chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                temperature=0.3,
                max_tokens=500,
                response_format={"type": "json_object"},
            )
        else:
            response = await _get_openai().chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.3,
                max_tokens=500,
                response_format={"type": "json_object"},
            )

        import json
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {
            "next_talking_point": "Continue the conversation naturally.",
            "objection_handling": "",
            "sentiment": "Neutral",
            "key_insight": f"AI suggestion unavailable: {str(e)}",
        }
