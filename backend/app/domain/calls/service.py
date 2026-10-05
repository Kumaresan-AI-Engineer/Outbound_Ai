"""Call lifecycle orchestration: persisting the transcript when a call ends
and kicking off post-call analysis."""

import asyncio
import logging

from bson import ObjectId

from app.domain.calls.follow_up import auto_schedule_unanswered_followup, parse_follow_up_date
from app.domain.calls.state import active_call_store
from app.repositories.call_logs_repo import call_logs_repo

logger = logging.getLogger(__name__)


async def save_and_cleanup(call_id: str, status: str = "completed") -> None:
    """Save transcript to DB and remove from the active call store. Called
    when a call truly ends."""
    call_data = active_call_store.get(call_id)
    if call_data and call_data.get("transcript"):
        try:
            await call_logs_repo.update_one(
                {"_id": ObjectId(call_id)},
                {
                    "$set": {
                        "transcript": call_data["transcript"],
                        "suggestions": call_data.get("suggestions", []),
                    }
                },
            )
            logger.info(f"[CALLS] Saved transcript for call {call_id}")
            # Fire background post-call analysis
            asyncio.create_task(
                _run_analysis(call_id, call_data["transcript"], call_data.get("contact_name", ""))
            )
        except Exception as e:
            logger.error(f"[CALLS] Failed to save transcript for call {call_id}: {e}")
    elif status == "failed":
        # Never answered (no-answer/busy/rejected/canceled) - there's no
        # transcript for the AI analyzer to work with, so the call would
        # otherwise vanish with zero follow-up tracking. Auto-schedule one.
        await auto_schedule_unanswered_followup(call_id)
    active_call_store.pop(call_id, None)


async def _run_analysis(call_id: str, transcript: str, contact_name: str = "") -> None:
    """Run AI post-call analysis in background and save to DB."""
    from app.ai.agents.analysis_agent import analyze_call

    try:
        logger.info(f"[ANALYSIS] Starting post-call analysis for {call_id}")
        analysis = await analyze_call(transcript, contact_name)

        update = {"analysis": analysis}

        # Parse follow-up date if needed
        if analysis.get("follow_up_needed"):
            follow_up_date = parse_follow_up_date(analysis.get("follow_up_date_suggestion", ""))
            update["follow_up_date"] = follow_up_date
            update["follow_up_status"] = "pending"
            logger.info(f"[ANALYSIS] Follow-up scheduled for {call_id}: {follow_up_date.date()}")

        await call_logs_repo.update_one({"_id": ObjectId(call_id)}, {"$set": update})
        logger.info(f"[ANALYSIS] Saved analysis for {call_id}")
    except Exception as e:
        logger.error(f"[ANALYSIS] Failed for {call_id}: {e}")
