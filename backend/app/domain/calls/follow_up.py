"""Follow-up scheduling: parsing the AI's free-text follow-up suggestion into
a real date, and the rule-based fallback for calls nobody answered (no
transcript exists for those, so there's nothing for the AI analyzer to work
with)."""

import logging
import re
from datetime import datetime, timedelta

from bson import ObjectId

from app.repositories.call_logs_repo import call_logs_repo

logger = logging.getLogger(__name__)


def parse_follow_up_date(suggestion: str) -> datetime:
    """Parse AI follow-up date suggestion like 'in 2 days', 'next week' into a real datetime."""
    now = datetime.utcnow()
    s = (suggestion or "").lower().strip()

    if not s:
        return now + timedelta(days=3)

    if "today" in s:
        return now
    if "tomorrow" in s:
        return now + timedelta(days=1)

    # "in X days" / "in X day"
    m = re.search(r"in\s+(\d+)\s+day", s)
    if m:
        return now + timedelta(days=int(m.group(1)))

    # "in X weeks" / "in X week"
    m = re.search(r"in\s+(\d+)\s+week", s)
    if m:
        return now + timedelta(weeks=int(m.group(1)))

    if "next week" in s:
        return now + timedelta(days=7)
    if "next month" in s:
        return now + timedelta(days=30)

    # "X days" without "in"
    m = re.search(r"(\d+)\s+day", s)
    if m:
        return now + timedelta(days=int(m.group(1)))

    return now + timedelta(days=3)


def suggest_reschedule(now: datetime) -> tuple[datetime, str]:
    """Default follow-up target for an unanswered call: 2 days out, nudged
    past the weekend to the following Monday rather than a Sat/Sun callback."""
    target = now + timedelta(days=2)
    if target.weekday() >= 5:  # Saturday=5, Sunday=6
        target += timedelta(days=7 - target.weekday())
        label = f"next Monday ({target.strftime('%b %d')})"
    else:
        label = f"in 2 days ({target.strftime('%b %d')})"
    return target, label


async def auto_schedule_unanswered_followup(call_id: str) -> None:
    """Rule-based follow-up for a call nobody picked up - no transcript
    means the AI analyzer has nothing to work with, so this fills the same
    analysis/follow_up shape by hand instead of letting the lead silently
    drop off the radar."""
    try:
        doc = await call_logs_repo.find_one({"_id": ObjectId(call_id)})
        if not doc or doc.get("analysis"):
            return  # already analyzed (e.g. a retry that did connect)
        contact_name = doc.get("contact_name") or "The client"
        target_date, label = suggest_reschedule(datetime.utcnow())
        analysis = {
            "summary": f"{contact_name} did not answer the call. Follow-up suggested {label}.",
            "sentiment": "Neutral",
            "quality_score": None,
            "went_well": [],
            "to_improve": [],
            "action_items": [],
            "follow_up_needed": True,
            "follow_up_reason": f"{contact_name} did not answer the call",
            "follow_up_date_suggestion": label,
            "key_points": [],
        }
        await call_logs_repo.update_one(
            {"_id": ObjectId(call_id)},
            {
                "$set": {
                    "analysis": analysis,
                    "follow_up_date": target_date,
                    "follow_up_status": "pending",
                }
            },
        )
        logger.info(f"[FOLLOW-UP] Auto-scheduled follow-up for unanswered call {call_id}: {label}")
    except Exception as e:
        logger.error(f"[FOLLOW-UP] Failed to auto-schedule follow-up for {call_id}: {e}")
