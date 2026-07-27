"""Confirms whether the OpenAI account can actually serve requests right now -
standalone, no MongoDB/Twilio/server needed, just the API key in backend/.env.

Reuses the REAL production prompt template and response parser from
suggestion_agent.py (not a reimplementation), and calls OpenAI the exact same
way _run_agent_once() does during a live call: same message shape, same
model, same response_format, same async client. If this succeeds, a live
call's suggestion request would succeed too.

Usage (from backend/, venv active) - either works:
    python -m scripts.test_openai_plan
    python scripts/test_openai_plan.py
"""

import sys
import asyncio
import json
import logging
from pathlib import Path

# Makes `app` importable regardless of how this script is invoked - running
# it directly (not via -m) only puts scripts/ on sys.path, not backend/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)-7s | %(message)s")

from app.services.ai_service import _get_openai
from app.services.suggestion_agent import SYSTEM_PROMPT, _parse_suggestion

OPENAI_MODEL = "gpt-4o"  # the model the app uses when AI_PROVIDER=openai

# A realistic mid-call transcript tail, shaped exactly like what
# _run_agent_once() builds from active_calls[call_id]["transcript"].
SAMPLE_TRANSCRIPT_TAIL = """[You]: Hi Ravi, thanks for taking the time today.
[Ravi]: Sure, no problem. What's this about?
[You]: We help banks streamline their loan approval process with AI.
[Ravi]: Interesting - right now our approval system runs on a legacy Oracle database and takes almost 24 hours to get a decision back to the customer.
[You]: That's a significant delay. What's driving the push to speed that up?
[Ravi]: Honestly, customer complaints. We're losing applicants to competitors who approve same-day."""


async def minimal_sanity_check() -> bool:
    """Cheapest possible call - just confirms auth + quota work at all,
    before spending tokens on the full realistic reproduction below."""
    print("--- Test 1: minimal sanity check (gpt-4o-mini, 5 tokens) ---")
    try:
        response = await _get_openai().chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Say OK"}],
            max_tokens=5,
        )
        print(f"PASS - response: {response.choices[0].message.content!r}\n")
        return True
    except Exception as e:
        print(f"FAIL - {type(e).__name__}: {e}\n")
        return False


async def realistic_suggestion_call() -> bool:
    """Reproduces the exact request _run_agent_once() sends to OpenAI during
    a real call - same prompt template, same params, same parser."""
    print(f"--- Test 2: realistic in-call suggestion request ({OPENAI_MODEL}) ---")
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT.format(
                contact_name="Ravi",
                company_part=" from FinEdge",
                elapsed="1m30s",
                project_context="",
            ),
        },
        {
            "role": "user",
            "content": f"Live transcript (most recent last):\n\n{SAMPLE_TRANSCRIPT_TAIL}\n\nProvide your coaching suggestion now.",
        },
    ]
    try:
        response = await _get_openai().chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.3,
            max_tokens=600,
            response_format={"type": "json_object"},
        )
        suggestion = _parse_suggestion(response.choices[0].message.content)
        if not suggestion:
            print("FAIL - call succeeded but response didn't parse as a valid suggestion\n")
            return False
        print("PASS - parsed suggestion:")
        print(json.dumps(suggestion, indent=2))
        print()
        return True
    except Exception as e:
        print(f"FAIL - {type(e).__name__}: {e}\n")
        return False


async def main():
    print("Testing whether the OpenAI account in backend/.env can serve real requests.\n")
    ok1 = await minimal_sanity_check()
    ok2 = await realistic_suggestion_call() if ok1 else False

    print("=" * 60)
    if ok1 and ok2:
        print("RESULT: OpenAI plan is WORKING - live-call suggestions would succeed on OpenAI.")
    elif ok1 and not ok2:
        print("RESULT: Basic auth/quota works, but the realistic call failed - see error above.")
    else:
        print("RESULT: OpenAI account is NOT currently serving requests - see error above.")
        print("Check platform.openai.com -> Settings -> Billing for payment method / usage limits.")


if __name__ == "__main__":
    asyncio.run(main())
