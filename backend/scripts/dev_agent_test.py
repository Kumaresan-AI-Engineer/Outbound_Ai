"""Dev-only: exercise the suggestion agent without making a phone call.

Usage (from backend/, venv active, MongoDB running):
    python -m scripts.dev_agent_test [contact_id] [--no-prefetch]

If contact_id is omitted, the first contact in the DB is used.
--no-prefetch skips cache warming to exercise the live-Mongo tool fallback.
"""

import sys
import json
import asyncio
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(levelname)-7s | %(message)s")

from bson import ObjectId
from app.routers.ws import active_calls
from app.database import contacts_collection
from app.services.suggestion_agent import prefetch_context, _run_agent_once

CANNED_LINES = [
    "[You]: Hi, this is Sarah from ABC Solutions, am I speaking with {name}?",
    "[{name}]: Yes, this is {name} speaking.",
    "[You]: Great, thanks for taking my call. I wanted to follow up on your interest in our automation platform.",
    "[{name}]: Right, I remember signing up for the demo.",
    "[You]: Based on what you saw, do you think it could fit your team's workflow?",
    "[{name}]: Honestly, we already use a competitor tool, and our budget is frozen this quarter.",
]


async def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    no_prefetch = "--no-prefetch" in sys.argv

    if args:
        contact = await contacts_collection.find_one({"_id": ObjectId(args[0])})
    else:
        contact = await contacts_collection.find_one()
    if not contact:
        print("No contact found - add a contact first or pass a contact_id")
        return

    contact_id = str(contact["_id"])
    name = contact["name"]
    print(f"Testing agent against contact: {name} ({contact_id})")
    print(f"Prefetch: {'OFF (live tool fallback)' if no_prefetch else 'ON'}\n")

    call_id = "dev-test"
    active_calls[call_id] = {
        "frontend_ws": None,
        "transcript": "\n".join(line.format(name=name) for line in CANNED_LINES),
        "suggestions": [],
        "contact_name": name,
        "contact_id": contact_id,
        "interims": {},
        "started_at": datetime.utcnow(),
        "agent_cache": None,
        "agent_pending": "we already use a competitor tool and our budget is frozen this quarter",
        "agent_running": False,
        "agent_dirty": False,
    }

    if not no_prefetch:
        await prefetch_context(call_id, contact_id)

    suggestion = await _run_agent_once(call_id)

    print("\n=== SUGGESTION ===")
    print(json.dumps(suggestion, indent=2) if suggestion else "None (agent failed - check logs)")


if __name__ == "__main__":
    asyncio.run(main())
