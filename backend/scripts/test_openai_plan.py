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

import asyncio
import json
import logging
import sys
from pathlib import Path

# Makes `app` importable regardless of how this script is invoked - running
# it directly (not via -m) only puts scripts/ on sys.path, not backend/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)-7s | %(message)s")

from app.ai.prompts.suggestion_prompts import build_coaching_messages
from app.ai.providers.factory import get_provider
from app.ai.schemas.suggestion import Suggestion

OPENAI_MODEL = "gpt-4o"  # the model the app uses when AI_PROVIDER=openai

# A realistic mid-call transcript tail, shaped exactly like what
# _run_agent_once() builds from the active call store's ["transcript"].
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
        response = await get_provider("openai").complete(
            [{"role": "user", "content": "Say OK"}], model="gpt-4o-mini", max_tokens=5
        )
        print(f"PASS - response: {response.content!r}\n")
        return True
    except Exception as e:
        print(f"FAIL - {type(e).__name__}: {e}\n")
        return False


async def realistic_suggestion_call() -> bool:
    """Reproduces the exact request _run_agent_once() sends to OpenAI during
    a real call - same prompt template, same params, same parser."""
    print(f"--- Test 2: realistic in-call suggestion request ({OPENAI_MODEL}) ---")
    messages = build_coaching_messages(
        contact_name="Ravi",
        company_part=" from FinEdge",
        elapsed="1m30s",
        project_context="",
        transcript_tail=SAMPLE_TRANSCRIPT_TAIL,
    )
    try:
        suggestion = await get_provider("openai").complete_structured(
            messages, Suggestion, model=OPENAI_MODEL, temperature=0.3, max_tokens=600
        )
        print("PASS - parsed suggestion:")
        print(json.dumps(suggestion.model_dump(), indent=2))
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
