"""Agentic in-call suggestion engine.

Triggered after each final contact utterance (speech_final from the
transcription layer). Runs the suggestion LLM and appends its structured
suggestion to active_calls[call_id]["suggestions"], which the frontend
already polls via GET /calls/live/{call_id}.

NOTE: tool-calling (CRM profile / past-call history lookups) is implemented
but currently DISABLED - see the commented TOOL SUPPORT sections below to
re-enable it.

Failure policy: the agent must NEVER break a call - every entry point
swallows and logs its own exceptions.
"""

import json
import asyncio
import logging
from datetime import datetime
from bson import ObjectId
from app.config import get_settings
from app.routers.ws import active_calls
from app.database import contacts_collection, call_logs_collection
from app.services.ai_service import _get_openai, _get_groq

logger = logging.getLogger(__name__)
settings = get_settings()

MODEL = "llama-3.3-70b-versatile"
AGENT_TIMEOUT = 12.0
MIN_NEW_WORDS = 3  # skip triggers on "yeah", "ok", etc.
TRANSCRIPT_TAIL_LINES = 25
PAST_CALLS_LIMIT = 3

# Fast Groq gate deciding whether THIS turn should pull our project portfolio
# into the coaching prompt - keeps the main GPT-4o suggestion firing on every
# turn as before, but only injects project context when it's actually asked
# for. See TECHNICAL_OVERVIEW discussion: benchmarked at ~130-330ms / ~88%
# accuracy on Groq vs 2.3s+ and broken output for local CPU-only SLMs.
#
# The same call also detects "is the client describing their own need" - used
# to trigger a live project match when nothing was pre-matched at Excel-import
# time (blank Project column, or a contact never imported at all). Once a
# live match succeeds it's locked into agent_cache for the rest of the call -
# no further re-matching, so recommendations stay consistent turn to turn.
PROJECT_INTENT_MODEL = "llama-3.1-8b-instant"
PROJECT_INTENT_TIMEOUT = 3.0
PROJECT_SIGNAL_PROMPT = """Analyze the customer's message during a live sales call and decide two things:
1. is_project_inquiry: are they asking about, or would they clearly benefit from hearing about, OUR company's past projects, case studies, or capabilities?
2. is_describing_own_need: are they describing THEIR OWN project, business problem, or requirement (what they're trying to build or solve)?

Respond with ONLY a JSON object: {"is_project_inquiry": true or false, "is_describing_own_need": true or false}"""

# ---------------------------------------------------------------------------
# TOOL SUPPORT - disabled for now; uncomment to re-enable agent tool-calling.
# When re-enabling, also restore the tool loop in _run_agent_once() and add
# this line back to SYSTEM_PROMPT:
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

SYSTEM_PROMPT = """You are a real-time AI sales coach assisting a business agent DURING a live outbound call with {contact_name}{company_part}. Call elapsed: {elapsed}.
{project_context}
Respond with a JSON object with exactly these fields:
{{
  "next_talking_point": "what the agent should say or ask next (1-2 sentences)",
  "objection_handling": "how to address any concern the prospect just raised (empty string if none)",
  "sentiment": "Positive" or "Neutral" or "Negative" (the prospect's current sentiment),
  "key_insight": "the single most important thing the prospect has revealed (empty string if none)",
  "recommended_project": "which ONE of our past projects to bring up right now, as 'Project Name — one-line pitch tailored to what the prospect just said' (empty string if none fits this moment)",
  "clarifying_question": "if the prospect just described a technical concept, system, tool, workflow, metric, or requirement, ONE specific, sharp follow-up question the BA should ask to dig deeper into it and uncover real requirements - empty string if they haven't said anything technical worth probing this turn"
}}

Keep advice concise, specific, and immediately actionable. Only fill clarifying_question when the prospect's last message actually contained technical detail worth following up on - don't force one every turn."""

PROJECT_CONTEXT_TEMPLATE = """
OUR COMPANY'S RELEVANT PAST PROJECTS — the client{client_domain_part}:
{project_lines}
Ground your coaching in these real projects: reference them by name with concrete outcomes instead of generic claims. Only recommend one when it genuinely fits the conversation.
"""


# ---------------------------------------------------------------- context

async def _fetch_profile(contact_id: str) -> dict | None:
    contact = await contacts_collection.find_one({"_id": ObjectId(contact_id)})
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
        call_logs_collection.find({"contact_id": contact_id, "status": "completed"})
        .sort("created_at", -1)
        .limit(PAST_CALLS_LIMIT)
    ):
        analysis = doc.get("analysis") or {}
        past.append({
            "date": doc["created_at"].isoformat(),
            "duration_seconds": doc.get("duration", 0),
            "summary": analysis.get("summary", ""),
            "sentiment": analysis.get("sentiment", ""),
            "action_items": analysis.get("action_items", []),
        })
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
            from app.services.client_agent import get_relevant_projects_for_contact
            cache["relevant_projects"] = await get_relevant_projects_for_contact(
                contact_id, (profile or {}).get("phone", "")
            )
        except Exception as e:
            logger.error(f"[AGENT] Project-context fetch failed for {call_id}: {e}")

        call_data = active_calls.get(call_id)
        if call_data is not None:
            call_data["agent_cache"] = cache
        logger.info(f"[AGENT] Prefetched context for call {call_id}")
    except Exception as e:
        logger.error(f"[AGENT] Prefetch failed for {call_id}: {e}")


def _build_project_context(relevant: dict | None) -> str:
    """Render the matched-projects block for the system prompt. Returns an
    empty string when the contact has no imported client record or matches."""
    if not relevant or not relevant.get("projects"):
        return ""
    client = relevant.get("client") or {}
    domain_part = f" is in the {client['domain']} domain" if client.get("domain") else ""
    if client.get("project"):
        domain_part += f"; their current initiative: {client['project']}"

    lines = []
    for i, p in enumerate(relevant["projects"], 1):
        bits = [f"{i}. {p['name']}"]
        if p.get("domain"):
            bits.append(f"[{p['domain']}]")
        if p.get("summary"):
            bits.append(f"— {p['summary']}")
        if p.get("key_features"):
            bits.append(f"Key features: {', '.join(p['key_features'])}.")
        if p.get("technologies"):
            bits.append(f"Tech: {', '.join(p['technologies'])}.")
        lines.append(" ".join(bits))

    return PROJECT_CONTEXT_TEMPLATE.format(
        client_domain_part=domain_part, project_lines="\n".join(lines)
    )


def _last_contact_utterance(call_data: dict) -> str:
    """Most recent finalized line from the contact (not the agent/"You"),
    used as the signal for the project-intent gate."""
    transcript = call_data.get("transcript", "")
    for line in reversed(transcript.split("\n")):
        if line and not line.startswith("[You]:"):
            return line.split("]: ", 1)[1] if "]: " in line else line
    return ""


async def _classify_project_signal(utterance: str) -> dict:
    """Fast Groq classification gate, one call covering two decisions:
    (a) show existing project context this turn, (b) the client is describing
    their own need, worth a live project-match attempt. Fails safe to both
    False - a missed signal costs a skipped suggestion, never a broken call."""
    default = {"is_project_inquiry": False, "is_describing_own_need": False}
    if not utterance.strip():
        return default
    try:
        response = await asyncio.wait_for(
            _get_groq().chat.completions.create(
                model=PROJECT_INTENT_MODEL,
                messages=[
                    {"role": "system", "content": PROJECT_SIGNAL_PROMPT},
                    {"role": "user", "content": f'Customer said: "{utterance}"'},
                ],
                temperature=0,
                max_tokens=30,
                response_format={"type": "json_object"},
            ),
            timeout=PROJECT_INTENT_TIMEOUT,
        )
        data = json.loads(response.choices[0].message.content)
        return {
            "is_project_inquiry": bool(data.get("is_project_inquiry", False)),
            "is_describing_own_need": bool(data.get("is_describing_own_need", False)),
        }
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
    call_data = active_calls.get(call_id)
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
            call_data = active_calls.get(call_id)
            if not call_data:
                return
            call_data["agent_dirty"] = False
            call_data["agent_pending"] = ""
            try:
                suggestion = await asyncio.wait_for(_run_agent_once(call_id), AGENT_TIMEOUT)
                call_data = active_calls.get(call_id)
                if suggestion and call_data is not None:
                    call_data.setdefault("suggestions", []).append(suggestion)
                    logger.info(f"[AGENT] Suggestion added for {call_id}")
            except asyncio.TimeoutError:
                logger.warning(f"[AGENT] Timed out for {call_id}, skipping")
            except Exception as e:
                logger.error(f"[AGENT] Failed for {call_id}: {e}")
            if not active_calls.get(call_id, {}).get("agent_dirty"):
                return
    finally:
        call_data = active_calls.get(call_id)
        if call_data is not None:
            call_data["agent_running"] = False


# ---------------------------------------------------------------- agent

def _parse_suggestion(content) -> dict | None:
    if not content:
        return None
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:]
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    recommended = data.get("recommended_project", "") or ""
    if isinstance(recommended, dict):  # tolerate {"name": ..., "pitch": ...}
        recommended = " — ".join(
            str(v) for v in (recommended.get("name"), recommended.get("pitch")) if v
        )
    suggestion = {
        "next_talking_point": str(data.get("next_talking_point", "") or ""),
        "objection_handling": str(data.get("objection_handling", "") or ""),
        "sentiment": data.get("sentiment") or "Neutral",
        "key_insight": str(data.get("key_insight", "") or ""),
        "recommended_project": str(recommended),
        "clarifying_question": str(data.get("clarifying_question", "") or ""),
    }
    if not suggestion["next_talking_point"] and not suggestion["objection_handling"]:
        return None
    return suggestion


async def _run_agent_once(call_id: str) -> dict | None:
    call_data = active_calls.get(call_id)
    if not call_data:
        return None
    transcript = call_data.get("transcript", "")
    if not transcript:
        return None

    tail = "\n".join(transcript.split("\n")[-TRANSCRIPT_TAIL_LINES:])
    contact_name = call_data.get("contact_name", "the prospect")
    if call_data.get("agent_cache") is None:
        call_data["agent_cache"] = {}
    cache = call_data["agent_cache"]  # live reference - mutations must persist to active_calls
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
        if (not relevant or not relevant.get("projects")) and signal["is_describing_own_need"]:
            from app.services.client_agent import match_projects_from_description
            live_match = await match_projects_from_description(last_utterance)
            if live_match:
                relevant = live_match
                cache["relevant_projects"] = relevant

        if relevant and relevant.get("projects") and signal["is_project_inquiry"]:
            project_context = _build_project_context(relevant)

    elapsed = "unknown"
    started = call_data.get("started_at")
    if started:
        secs = int((datetime.utcnow() - started).total_seconds())
        elapsed = f"{secs // 60}m{secs % 60:02d}s"

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT.format(
                contact_name=contact_name,
                company_part=company_part,
                elapsed=elapsed,
                project_context=project_context,
            ),
        },
        {
            "role": "user",
            "content": f"Live transcript (most recent last):\n\n{tail}\n\nProvide your coaching suggestion now.",
        },
    ]
    client = _get_groq()

    # TOOL SUPPORT - disabled for now. To re-enable, replace the single call
    # below with this tool-calling loop (and uncomment TOOLS/_execute_tool):
    #
    # for _ in range(MAX_TOOL_ROUNDS):
    #     response = await client.chat.completions.create(
    #         model=MODEL,
    #         messages=messages,
    #         tools=TOOLS,
    #         tool_choice="auto",
    #         temperature=0.3,
    #         max_tokens=600,
    #     )
    #     msg = response.choices[0].message
    #     if msg.tool_calls:
    #         messages.append({
    #             "role": "assistant",
    #             "content": msg.content,
    #             "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
    #         })
    #         for tc in msg.tool_calls:
    #             logger.info(f"[AGENT] Tool call: {tc.function.name}")
    #             result = await _execute_tool(call_id, tc.function.name)
    #             messages.append({
    #                 "role": "tool",
    #                 "tool_call_id": tc.id,
    #                 "content": result,
    #             })
    #         continue
    #     parsed = _parse_suggestion(msg.content)
    #     if parsed:
    #         return parsed
    #     messages.append({"role": "assistant", "content": msg.content or ""})
    #     break
    #
    # messages.append({"role": "user", "content": "Respond now with the final JSON only."})

    response = await client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.3,
        max_tokens=600,
        response_format={"type": "json_object"},
    )
    return _parse_suggestion(response.choices[0].message.content)
