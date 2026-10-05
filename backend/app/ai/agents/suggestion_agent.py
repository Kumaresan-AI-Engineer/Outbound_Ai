"""Agentic in-call suggestion engine.

Triggered after each final contact utterance (speech_final from the
transcription layer). Runs the suggestion LLM and appends its structured
suggestion to the active call store's ["suggestions"] list for this call_id,
which the frontend already polls via GET /calls/live/{call_id}.

NOTE: tool-calling (CRM profile / past-call history lookups) is implemented
but currently DISABLED - see the commented TOOL SUPPORT sections below to
re-enable it.

NOTE: this agent deliberately always talks to Groq (not settings.ai_provider)
for both the coaching call and the fast intent gate - see the latency/
accuracy rationale in the PROJECT_INTENT_MODEL comment below. That predates
this refactor and is preserved as-is.

Failure policy: the agent must NEVER break a call - every entry point
swallows and logs its own exceptions.
"""

import asyncio
import logging
from datetime import datetime

from bson import ObjectId

from app.ai.prompts.suggestion_prompts import (
    build_coaching_messages,
    build_project_context,
    build_project_signal_messages,
)
from app.ai.providers.base import LLMValidationError
from app.ai.providers.factory import get_provider
from app.ai.schemas.suggestion import ProjectSignal, Suggestion
from app.config import get_settings
from app.domain.calls.state import active_call_store
from app.repositories.call_logs_repo import call_logs_repo
from app.repositories.contacts_repo import contacts_repo

logger = logging.getLogger(__name__)
settings = get_settings()

MODEL = settings.groq_model
AGENT_TIMEOUT = 12.0
MIN_NEW_WORDS = 3  # skip triggers on "yeah", "ok", etc.
TRANSCRIPT_TAIL_LINES = 25
PAST_CALLS_LIMIT = 3

# Fast Groq gate deciding whether THIS turn should pull our project portfolio
# into the coaching prompt - keeps the main suggestion model firing on every
# turn as before, but only injects project context when it's actually asked
# for. Originally benchmarked against llama-3.1-8b-instant (~130-330ms /
# ~88% accuracy on Groq vs 2.3s+ and broken output for local CPU-only SLMs);
# that model (and MODEL's prior llama-3.3-70b-versatile) stopped being
# available to this account's Groq API key, hence the openai/gpt-oss-*
# swap here and in MODEL above - not yet re-benchmarked against those numbers.
#
# The same call also detects "is the client describing their own need" - used
# to trigger a live project match when nothing was pre-matched at Excel-import
# time (blank Project column, or a contact never imported at all). Once a
# live match succeeds it's locked into agent_cache for the rest of the call -
# no further re-matching, so recommendations stay consistent turn to turn.
PROJECT_INTENT_MODEL = settings.groq_fast_model
PROJECT_INTENT_TIMEOUT = 3.0

# ---------------------------------------------------------------------------
# TOOL SUPPORT - disabled for now; uncomment to re-enable agent tool-calling.
# When re-enabling, also restore the tool loop in _run_agent_once() and add
# this line back to SYSTEM_PROMPT (app/ai/prompts/suggestion_prompts.py):
#   "You have tools to look up the contact's CRM profile and past call
#    history. Use them when they would sharpen your advice (earlier
#    commitments, notes, previous objections) - but do not call the same
#    tool twice."
# ---------------------------------------------------------------------------
# MAX_TOOL_ROUNDS = 3
#
# TOOLS = [
#     {
#         "type": "function",
#         "function": {
#             "name": "get_contact_profile",
#             "description": "Get the contact's CRM profile: company, status, notes, and when they were last called.",
#             "parameters": {"type": "object", "properties": {}, "required": []},
#         },
#     },
#     {
#         "type": "function",
#         "function": {
#             "name": "get_past_calls",
#             "description": "Get summaries of the last few completed calls with this contact: date, duration, summary, sentiment, and action items.",
#             "parameters": {"type": "object", "properties": {}, "required": []},
#         },
#     },
# ]


# ---------------------------------------------------------------- context


async def _fetch_profile(contact_id: str) -> dict | None:
    contact = await contacts_repo.find_one({"_id": ObjectId(contact_id)})
    if not contact:
        return None
    return {
        "name": contact.get("name", ""),
        "company": contact.get("company", ""),
        "phone": contact.get("phone", ""),
        "status": contact.get("status", ""),
        "notes": contact.get("notes", ""),
        "last_called": contact["last_called"].isoformat() if contact.get("last_called") else None,
    }


async def _fetch_past_calls(contact_id: str) -> list:
    past = []
    async for doc in (
        call_logs_repo.find({"contact_id": contact_id, "status": "completed"})
        .sort("created_at", -1)
        .limit(PAST_CALLS_LIMIT)
    ):
        analysis = doc.get("analysis") or {}
        past.append(
            {
                "date": doc["created_at"].isoformat(),
                "duration_seconds": doc.get("duration", 0),
                "summary": analysis.get("summary", ""),
                "sentiment": analysis.get("sentiment", ""),
                "action_items": analysis.get("action_items", []),
            }
        )
    return past


async def prefetch_context(call_id: str, contact_id: str) -> None:
    """Warm the agent's tool cache at call start so tool rounds cost only
    the LLM round-trip, not a Mongo wait."""
    try:
        profile = await _fetch_profile(contact_id)
        cache = {
            "contact_profile": profile,
            "past_calls": await _fetch_past_calls(contact_id),
            "relevant_projects": None,
        }
        # Imported clients carry a domain + matched internal projects — feed
        # them to the agent so suggestions reference real past work.
        try:
            from app.ai.agents.client_domain_agent import get_relevant_projects_for_contact

            cache["relevant_projects"] = await get_relevant_projects_for_contact(
                contact_id, (profile or {}).get("phone", "")
            )
        except Exception as e:
            logger.error(f"[AGENT] Project-context fetch failed for {call_id}: {e}")

        call_data = active_call_store.get(call_id)
        if call_data is not None:
            call_data["agent_cache"] = cache
        logger.info(f"[AGENT] Prefetched context for call {call_id}")
    except Exception as e:
        logger.error(f"[AGENT] Prefetch failed for {call_id}: {e}")


def _last_contact_utterance(call_data: dict) -> str:
    """Most recent finalized line from the contact (not the agent/"You"),
    used as the signal for the project-intent gate."""
    transcript = call_data.get("transcript", "")
    for line in reversed(transcript.split("\n")):
        if line and not line.startswith("[You]:"):
            return line.split("]: ", 1)[1] if "]: " in line else line
    return ""


async def _classify_project_signal(utterance: str) -> ProjectSignal:
    """Fast Groq classification gate, one call covering two decisions:
    (a) show existing project context this turn, (b) the client is describing
    their own need, worth a live project-match attempt. Fails safe to both
    False - a missed signal costs a skipped suggestion, never a broken call."""
    default = ProjectSignal()
    if not utterance.strip():
        return default
    try:
        return await asyncio.wait_for(
            get_provider("groq").complete_structured(
                build_project_signal_messages(utterance),
                ProjectSignal,
                model=PROJECT_INTENT_MODEL,
                temperature=0,
                max_tokens=30,
            ),
            timeout=PROJECT_INTENT_TIMEOUT,
        )
    except Exception as e:
        logger.warning(f"[AGENT] Project-signal gate failed, skipping context: {e}")
        return default


# TOOL SUPPORT - disabled for now; uncomment together with TOOLS above.
# async def _execute_tool(call_id: str, name: str) -> str:
#     call_data = active_calls.get(call_id) or {}
#     cache = call_data.get("agent_cache") or {}
#     contact_id = call_data.get("contact_id")
#     try:
#         if name == "get_contact_profile":
#             profile = cache.get("contact_profile")
#             if profile is None and contact_id:
#                 profile = await _fetch_profile(contact_id)
#             return json.dumps(profile or {"error": "profile unavailable"})
#         if name == "get_past_calls":
#             past = cache.get("past_calls")
#             if past is None and contact_id:
#                 past = await _fetch_past_calls(contact_id)
#             return json.dumps({"past_calls": past or []})
#     except Exception as e:
#         logger.error(f"[AGENT] Tool {name} failed: {e}")
#         return json.dumps({"error": str(e)})
#     return json.dumps({"error": "unknown tool"})


# ---------------------------------------------------------------- trigger


def maybe_trigger_suggestion(call_id: str) -> None:
    """Sync, safe to call from transcript callbacks. Single-flight per call;
    triggers while a run is in-flight coalesce into one dirty re-run."""
    call_data = active_call_store.get(call_id)
    if not call_data or not settings.suggestion_agent_enabled:
        return
    if len(call_data.get("agent_pending", "").split()) < MIN_NEW_WORDS:
        return
    if call_data.get("agent_running"):
        call_data["agent_dirty"] = True
        return
    call_data["agent_running"] = True
    asyncio.create_task(_agent_worker(call_id))


async def _agent_worker(call_id: str) -> None:
    try:
        while True:
            call_data = active_call_store.get(call_id)
            if not call_data:
                return
            call_data["agent_dirty"] = False
            call_data["agent_pending"] = ""
            try:
                suggestion = await asyncio.wait_for(_run_agent_once(call_id), AGENT_TIMEOUT)
                call_data = active_call_store.get(call_id)
                if suggestion and call_data is not None:
                    call_data.setdefault("suggestions", []).append(suggestion)
                    logger.info(f"[AGENT] Suggestion added for {call_id}")
            except asyncio.TimeoutError:
                logger.warning(f"[AGENT] Timed out for {call_id}, skipping")
            except Exception as e:
                logger.error(f"[AGENT] Failed for {call_id}: {e}")
            if not (active_call_store.get(call_id) or {}).get("agent_dirty"):
                return
    finally:
        call_data = active_call_store.get(call_id)
        if call_data is not None:
            call_data["agent_running"] = False


# ---------------------------------------------------------------- agent


async def _run_agent_once(call_id: str) -> dict | None:
    call_data = active_call_store.get(call_id)
    if not call_data:
        return None
    transcript = call_data.get("transcript", "")
    if not transcript:
        return None

    tail = "\n".join(transcript.split("\n")[-TRANSCRIPT_TAIL_LINES:])
    contact_name = call_data.get("contact_name", "the prospect")
    if call_data.get("agent_cache") is None:
        call_data["agent_cache"] = {}
    cache = call_data["agent_cache"]  # live reference - mutations must persist to the active call store
    profile = cache.get("contact_profile") or {}
    company_part = f" from {profile['company']}" if profile.get("company") else ""

    relevant = cache.get("relevant_projects")
    project_context = ""
    last_utterance = _last_contact_utterance(call_data)
    if last_utterance:
        signal = await _classify_project_signal(last_utterance)

        # Nothing pre-matched yet (blank Excel Project field, or a contact
        # never imported at all) - if the client is describing their own
        # need, try a live match. Once one succeeds it's locked into the
        # cache, so this only runs until a match is found, never after.
        if (not relevant or not relevant.get("projects")) and signal.is_describing_own_need:
            from app.ai.agents.client_domain_agent import match_projects_from_description

            live_match = await match_projects_from_description(last_utterance)
            if live_match:
                relevant = live_match
                cache["relevant_projects"] = relevant

        if relevant and relevant.get("projects") and signal.is_project_inquiry:
            project_context = build_project_context(relevant)

    elapsed = "unknown"
    started = call_data.get("started_at")
    if started:
        secs = int((datetime.utcnow() - started).total_seconds())
        elapsed = f"{secs // 60}m{secs % 60:02d}s"

    messages = build_coaching_messages(contact_name, company_part, elapsed, project_context, tail)

    # TOOL SUPPORT - disabled for now. To re-enable, replace the single call
    # below with this tool-calling loop (and uncomment TOOLS/_execute_tool):
    #
    # provider = get_provider("groq")
    # for _ in range(MAX_TOOL_ROUNDS):
    #     response = await provider.complete(
    #         messages, model=MODEL, tools=TOOLS, tool_choice="auto",
    #         temperature=0.3, max_tokens=600,
    #     )
    #     if response.tool_calls:
    #         messages.append({
    #             "role": "assistant",
    #             "content": response.content,
    #             "tool_calls": [
    #                 {"id": tc.id, "type": "function",
    #                  "function": {"name": tc.name, "arguments": tc.arguments}}
    #                 for tc in response.tool_calls
    #             ],
    #         })
    #         for tc in response.tool_calls:
    #             logger.info(f"[AGENT] Tool call: {tc.name}")
    #             result = await _execute_tool(call_id, tc.name)
    #             messages.append({
    #                 "role": "tool", "tool_call_id": tc.id, "content": result,
    #             })
    #         continue
    #     break
    #
    # messages.append({"role": "user", "content": "Respond now with the final JSON only."})

    try:
        suggestion = await get_provider("groq").complete_structured(
            messages, Suggestion, model=MODEL, temperature=0.3, max_tokens=600
        )
    except LLMValidationError:
        return None
    return suggestion.model_dump() if suggestion.is_actionable() else None
