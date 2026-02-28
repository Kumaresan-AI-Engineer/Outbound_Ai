import json
import re
import asyncio
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
from bson import ObjectId
from app.database import call_logs_collection

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

router = APIRouter()

# Track active calls: call_id -> {frontend_ws, transcript, suggestions, ...}
active_calls: dict = {}


@router.websocket("/ws/call/{call_id}")
async def frontend_websocket(websocket: WebSocket, call_id: str):
    """WebSocket for frontend to receive live transcript and suggestions."""
    await websocket.accept()
    logger.info(f"[FRONTEND WS] Connected for call: {call_id}")

    if call_id not in active_calls:
        active_calls[call_id] = {
            "frontend_ws": websocket,
            "transcript": "",
            "suggestions": [],
        }
    else:
        # Reconnect: preserve existing transcript, just update the ws reference
        active_calls[call_id]["frontend_ws"] = websocket

    async def ping_loop():
        """Send periodic pings to keep the connection alive."""
        try:
            while True:
                await asyncio.sleep(5)
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                else:
                    break
        except Exception:
            pass

    ping_task = asyncio.create_task(ping_loop())

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "change_provider":
                active_calls[call_id]["ai_provider"] = msg.get("provider", "groq")
            elif msg.get("type") == "end_call":
                logger.info(f"[FRONTEND WS] End call signal for: {call_id}")
                break
            elif msg.get("type") == "pong":
                pass  # keepalive response from client
    except WebSocketDisconnect:
        logger.info(f"[FRONTEND WS] Disconnected for call: {call_id}")
    except Exception as e:
        logger.error(f"[FRONTEND WS] Error for call {call_id}: {e}")
    finally:
        ping_task.cancel()
        # Don't pop active_calls — frontend may reconnect
        if call_id in active_calls:
            active_calls[call_id]["frontend_ws"] = None


async def save_and_cleanup(call_id: str):
    """Save transcript to DB and remove from active_calls. Called when call truly ends."""
    call_data = active_calls.get(call_id)
    if call_data and call_data.get("transcript"):
        try:
            await call_logs_collection.update_one(
                {"_id": ObjectId(call_id)},
                {"$set": {
                    "transcript": call_data["transcript"],
                    "suggestions": call_data.get("suggestions", []),
                }},
            )
            logger.info(f"[WS] Saved transcript for call {call_id}")
            # Fire background post-call analysis
            asyncio.create_task(_run_analysis(call_id, call_data["transcript"]))
        except Exception as e:
            logger.error(f"[WS] Failed to save transcript for call {call_id}: {e}")
    active_calls.pop(call_id, None)


def _parse_follow_up_date(suggestion: str) -> datetime:
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


async def _run_analysis(call_id: str, transcript: str):
    """Run AI post-call analysis in background and save to DB."""
    from app.services.ai_service import analyze_call
    try:
        logger.info(f"[ANALYSIS] Starting post-call analysis for {call_id}")
        analysis = await analyze_call(transcript)

        update = {"analysis": analysis}

        # Parse follow-up date if needed
        if analysis.get("follow_up_needed"):
            follow_up_date = _parse_follow_up_date(analysis.get("follow_up_date_suggestion", ""))
            update["follow_up_date"] = follow_up_date
            update["follow_up_status"] = "pending"
            logger.info(f"[ANALYSIS] Follow-up scheduled for {call_id}: {follow_up_date.date()}")

        await call_logs_collection.update_one(
            {"_id": ObjectId(call_id)},
            {"$set": update},
        )
        logger.info(f"[ANALYSIS] Saved analysis for {call_id}")
    except Exception as e:
        logger.error(f"[ANALYSIS] Failed for {call_id}: {e}")
