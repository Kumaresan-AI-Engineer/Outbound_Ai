import json
import asyncio
import logging
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import Response
from twilio.twiml.voice_response import VoiceResponse
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant
from bson import ObjectId
from datetime import datetime, timedelta
from app.database import contacts_collection, call_logs_collection
from app.config import get_settings
from app.models.schemas import CallInitiateRequest, CallLogResponse
from app.services.twilio_service import generate_twiml_for_browser
from app.routers.ws import active_calls, save_and_cleanup

logger = logging.getLogger(__name__)
settings = get_settings()
_analysis_in_progress: set = set()  # Guard against duplicate triggers
_analysis_attempts: dict = {}  # call_id -> attempt count, caps retries on a persistently-failing call
MAX_ANALYSIS_ATTEMPTS = 3


router = APIRouter(prefix="/calls", tags=["calls"])


@router.get("/token")
async def get_voice_token():
    """Generate a Twilio Access Token with Voice grant for browser calling."""
    token = AccessToken(
        settings.twilio_account_sid,
        settings.twilio_api_key,
        settings.twilio_api_secret,
        identity="ba-user",
    )
    voice_grant = VoiceGrant(
        outgoing_application_sid=settings.twilio_twiml_app_sid,
    )
    token.add_grant(voice_grant)
    return {"token": token.to_jwt()}


@router.post("/initiate")
async def initiate(req: CallInitiateRequest):
    """Create a call log entry. The actual call is made from the browser via Twilio Client SDK."""
    contact = await contacts_collection.find_one({"_id": ObjectId(req.contact_id)})
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    call_log = {
        "contact_id": req.contact_id,
        "contact_name": contact["name"],
        "phone": req.phone,
        "status": "initiating",
        "duration": 0,
        "transcript": "",
        "suggestions": [],
        "created_at": datetime.utcnow(),
    }
    result = await call_logs_collection.insert_one(call_log)
    call_id = str(result.inserted_id)

    # Pre-populate active_calls with contact info for transcript labeling
    # and the in-call suggestion agent
    active_calls[call_id] = {
        "frontend_ws": None,
        "transcript": "",
        "suggestions": [],
        "contact_name": contact["name"],
        "contact_id": req.contact_id,
        "interims": {},
        "started_at": datetime.utcnow(),
        "agent_cache": None,
        "agent_pending": "",
        "agent_running": False,
        "agent_dirty": False,
    }

    # Warm the agent's tool cache in the background
    from app.services.suggestion_agent import prefetch_context
    asyncio.create_task(prefetch_context(call_id, req.contact_id))

    return {"call_id": call_id, "status": "initiating"}


@router.post("/twiml-app")
async def twiml_app_webhook(request: Request):
    """TwiML App webhook — called by Twilio when browser initiates an outgoing call."""
    form_data = await request.form()
    all_fields = {k: v for k, v in form_data.items()}
    logger.info(f"[TWIML-APP] All fields: {all_fields}")

    to_number = form_data.get("To", "")
    call_id = form_data.get("callId", "")

    logger.info(f"[TWIML-APP] Browser call: to={to_number}, callId={call_id}")

    if not to_number or not call_id:
        response = VoiceResponse()
        response.say("Missing call parameters.")
        response.hangup()
        return Response(content=str(response), media_type="application/xml")

    # Update call log with Twilio call SID
    call_sid = form_data.get("CallSid", "")
    if call_sid and call_id:
        try:
            await call_logs_collection.update_one(
                {"_id": ObjectId(call_id)},
                {"$set": {"twilio_sid": call_sid, "status": "initiated"}},
            )
        except Exception as e:
            logger.error(f"[TWIML-APP] Failed to update call log: {e}")

    twiml = generate_twiml_for_browser(call_id, to_number)
    logger.info(f"[TWIML-APP] Generated TwiML: {twiml}")
    return Response(content=twiml, media_type="application/xml")


@router.post("/twiml/{call_id}")
async def twiml_webhook(call_id: str, to_number: str = ""):
    from app.services.twilio_service import generate_twiml
    twiml = generate_twiml(call_id, to_number)
    return Response(content=twiml, media_type="application/xml")


@router.post("/dial-complete/{call_id}")
async def dial_complete(call_id: str):
    """Called when the bridged call ends."""
    response = VoiceResponse()
    response.hangup()
    return Response(content=str(response), media_type="application/xml")


@router.post("/transcription/{call_id}")
async def transcription_webhook(call_id: str, request: Request):
    """Receives real-time transcription events from Twilio."""
    body = await request.body()
    logger.info(f"[TWILIO TRANSCRIPTION] call={call_id} raw body: {body.decode('utf-8', errors='replace')}")

    form_data = await request.form()
    all_fields = {k: v for k, v in form_data.items()}
    logger.info(f"[TWILIO TRANSCRIPTION] call={call_id} fields: {all_fields}")

    text = (
        form_data.get("TranscriptionText", "")
        or form_data.get("Transcript", "")
        or form_data.get("transcript", "")
        or ""
    )
    track = form_data.get("Track", form_data.get("track", ""))
    is_final = form_data.get("Final", form_data.get("final", "false")).lower() == "true"

    if not text:
        td = form_data.get("TranscriptionData", "")
        if td:
            try:
                data = json.loads(td)
                text = data.get("transcript", "") or data.get("text", "")
            except (json.JSONDecodeError, TypeError):
                pass

    if text:
        call_data = active_calls.get(call_id)
        contact_name = call_data.get("contact_name", "Client") if call_data else "Client"

        # Detect speaker from track label
        track_lower = str(track).lower()
        if "agent" in track_lower or "inbound" in track_lower:
            speaker = "You"
        elif "customer" in track_lower or "outbound" in track_lower:
            speaker = contact_name
        else:
            speaker = "Unknown"

        logger.info(f"[TWILIO TRANSCRIPTION] [{speaker}] track={track} final={is_final}: {text}")

        if call_data:
            if is_final:
                # Final — append to transcript
                labeled = f"[{speaker}]: {text}"
                call_data["transcript"] += f"\n{labeled}" if call_data["transcript"] else labeled
                # Clear interim for this speaker
                call_data.get("interims", {}).pop(speaker, None)
            else:
                # Interim — store latest per speaker (don't append to transcript)
                if "interims" not in call_data:
                    call_data["interims"] = {}
                call_data["interims"][speaker] = text

    return {"status": "ok"}


@router.post("/status/{call_id}")
async def status_callback(
    call_id: str, request: Request, CallStatus: str = Form(""), CallDuration: str = Form("0")
):
    form_data = await request.form()
    logger.info(f"[STATUS] call={call_id} fields: {dict(form_data)}")

    status_map = {
        "initiated": "initiated",
        "ringing": "ringing",
        "in-progress": "in_progress",
        "completed": "completed",
        "busy": "failed",
        "no-answer": "failed",
        "canceled": "failed",
        "failed": "failed",
    }
    mapped_status = status_map.get(CallStatus, CallStatus)
    logger.info(f"[STATUS] call={call_id} CallStatus={CallStatus!r} -> mapped_status={mapped_status!r}")

    # The live-poll endpoint reads this while the call is still in-flight -
    # without it, /calls/live has no way to tell "ringing" apart from
    # "genuinely answered" and was reporting a hardcoded "active" the whole
    # time, which broke every downstream "was this call actually picked up?"
    # check (including the secondary-number retry).
    if call_id in active_calls:
        active_calls[call_id]["twilio_status"] = mapped_status

    update = {"status": mapped_status}
    if CallDuration:
        update["duration"] = int(CallDuration)

    if mapped_status == "completed":
        try:
            call_doc = await call_logs_collection.find_one({"_id": ObjectId(call_id)})
            if call_doc:
                await contacts_collection.update_one(
                    {"_id": ObjectId(call_doc["contact_id"])},
                    {"$set": {"last_called": datetime.utcnow(), "status": "called"}},
                )
        except Exception as e:
            logger.error(f"[STATUS] Failed to update contact: {e}")

    # Also save transcript from active_calls if available
    call_data = active_calls.get(call_id)
    if call_data and call_data.get("transcript"):
        update["transcript"] = call_data["transcript"]
        update["suggestions"] = call_data.get("suggestions", [])

    await call_logs_collection.update_one(
        {"_id": ObjectId(call_id)}, {"$set": update}
    )

    # Notify frontend via WebSocket
    if call_id in active_calls:
        ws = active_calls[call_id].get("frontend_ws")
        if ws:
            try:
                await ws.send_text(
                    json.dumps({"type": "call_status", "status": mapped_status})
                )
            except Exception as e:
                logger.error(f"[STATUS] Failed to notify frontend for call {call_id}: {e}")

    if mapped_status in ("completed", "failed"):
        await save_and_cleanup(call_id, mapped_status)

    return {"status": "ok"}


@router.get("/live/{call_id}")
async def get_live_transcript(call_id: str):
    """Poll endpoint for live transcript, call status, and client context."""
    call_data = active_calls.get(call_id)
    if call_data:
        # Build full text: committed transcript + any pending interims
        full = call_data.get("transcript", "")
        interims = call_data.get("interims", {})
        for speaker, text in interims.items():
            interim_line = f"[{speaker}]: {text}"
            full += f"\n{interim_line}" if full else interim_line

        agent_cache = call_data.get("agent_cache") or {}
        return {
            "transcript": full,
            "interims": interims,
            "suggestions": call_data.get("suggestions", []),
            "status": call_data.get("twilio_status") or "initiating",
            "contact_profile": agent_cache.get("contact_profile"),
            "relevant_projects": agent_cache.get("relevant_projects"),
        }
    # Fall back to DB if call ended
    doc = await call_logs_collection.find_one({"_id": ObjectId(call_id)})
    if doc:
        return {
            "transcript": doc.get("transcript", ""),
            "interims": {},
            "suggestions": doc.get("suggestions", []),
            "status": doc.get("status", "unknown"),
            "contact_profile": None,
            "relevant_projects": None,
        }
    return {
        "transcript": "", "interims": {}, "suggestions": [], "status": "unknown",
        "contact_profile": None, "relevant_projects": None,
    }


@router.get("/analytics")
async def get_analytics():
    """Aggregated analytics for the dashboard."""
    now = datetime.utcnow()
    thirty_days_ago = now - timedelta(days=30)
    seven_days_ago = now - timedelta(days=7)

    # Total / completed / failed / avg duration
    pipeline_counts = [
        {"$group": {
            "_id": None,
            "total": {"$sum": 1},
            "completed": {"$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}},
            "failed": {"$sum": {"$cond": [{"$eq": ["$status", "failed"]}, 1, 0]}},
            "avg_duration": {"$avg": "$duration"},
            "total_duration": {"$sum": "$duration"},
        }}
    ]
    counts_result = await call_logs_collection.aggregate(pipeline_counts).to_list(1)
    counts = counts_result[0] if counts_result else {
        "total": 0, "completed": 0, "failed": 0, "avg_duration": 0, "total_duration": 0
    }

    # Quality + sentiment from analyzed calls
    pipeline_quality = [
        {"$match": {"status": "completed", "analysis": {"$exists": True, "$ne": None}}},
        {"$group": {
            "_id": None,
            "avg_quality": {"$avg": "$analysis.quality_score"},
            "sentiments": {"$push": "$analysis.sentiment"},
        }}
    ]
    quality_result = await call_logs_collection.aggregate(pipeline_quality).to_list(1)
    avg_quality = 0.0
    sentiment_breakdown = {"Positive": 0, "Neutral": 0, "Negative": 0}
    if quality_result:
        avg_quality = round(quality_result[0].get("avg_quality") or 0, 1)
        for s in quality_result[0].get("sentiments", []):
            if s in sentiment_breakdown:
                sentiment_breakdown[s] += 1

    # Follow-ups needed (pending only)
    follow_ups_needed = await call_logs_collection.count_documents(
        {"analysis.follow_up_needed": True, "follow_up_status": {"$ne": "completed"}}
    )

    # Follow-ups due today
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    follow_ups_today = await call_logs_collection.count_documents({
        "follow_up_status": "pending",
        "follow_up_date": {"$lte": today_end},
    })

    # Calls by date (last 30 days)
    pipeline_by_date = [
        {"$match": {"created_at": {"$gte": thirty_days_ago}}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ]
    raw_by_date = await call_logs_collection.aggregate(pipeline_by_date).to_list(31)
    calls_by_date = [{"date": d["_id"], "count": d["count"]} for d in raw_by_date]

    # Quality trend (last 7 days)
    pipeline_trend = [
        {"$match": {
            "created_at": {"$gte": seven_days_ago},
            "status": "completed",
            "analysis": {"$exists": True, "$ne": None}
        }},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
            "avg_score": {"$avg": "$analysis.quality_score"}
        }},
        {"$sort": {"_id": 1}}
    ]
    raw_trend = await call_logs_collection.aggregate(pipeline_trend).to_list(7)
    recent_quality_trend = [
        {"date": d["_id"], "avg_score": round(d["avg_score"] or 0, 1)}
        for d in raw_trend
    ]

    # Top action items
    pipeline_actions = [
        {"$match": {"analysis.action_items": {"$exists": True, "$ne": []}}},
        {"$unwind": "$analysis.action_items"},
        {"$group": {"_id": "$analysis.action_items", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 8}
    ]
    raw_actions = await call_logs_collection.aggregate(pipeline_actions).to_list(8)
    top_action_items = [{"item": a["_id"], "count": a["count"]} for a in raw_actions]

    return {
        "total_calls": counts.get("total", 0),
        "completed_calls": counts.get("completed", 0),
        "failed_calls": counts.get("failed", 0),
        "avg_duration": round(counts.get("avg_duration") or 0),
        "total_duration": counts.get("total_duration", 0),
        "avg_quality_score": avg_quality,
        "sentiment_breakdown": sentiment_breakdown,
        "calls_by_date": calls_by_date,
        "follow_ups_needed": follow_ups_needed,
        "follow_ups_today": follow_ups_today,
        "top_action_items": top_action_items,
        "recent_quality_trend": recent_quality_trend,
    }


@router.post("/weekly-summary")
async def weekly_summary():
    """Generate AI-powered weekly summary of call performance."""
    from app.services.ai_service import generate_weekly_summary

    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    docs = await call_logs_collection.find({
        "created_at": {"$gte": seven_days_ago},
        "status": "completed"
    }).to_list(200)

    if not docs:
        return {"summary": "No completed calls in the past 7 days."}

    lines = []
    for d in docs:
        a = d.get("analysis", {}) or {}
        lines.append(
            f"- {d['contact_name']} | sentiment:{a.get('sentiment', '?')} "
            f"| score:{a.get('quality_score', '?')} "
            f"| follow_up:{a.get('follow_up_needed', False)} "
            f"| actions: {'; '.join(a.get('action_items', []))}"
        )
    digest = "\n".join(lines)

    result = await generate_weekly_summary(digest, len(docs))
    return result


@router.get("/follow-ups")
async def get_follow_ups():
    """Get all calls that need follow-up (pending only)."""
    results = []
    async for doc in call_logs_collection.find(
        {"analysis.follow_up_needed": True, "follow_up_status": {"$ne": "completed"}}
    ).sort("follow_up_date", 1):
        a = doc.get("analysis", {}) or {}
        fu_date = doc.get("follow_up_date")
        results.append({
            "id": str(doc["_id"]),
            "contact_id": doc["contact_id"],
            "contact_name": doc["contact_name"],
            "phone": doc["phone"],
            "call_date": doc["created_at"].isoformat(),
            "sentiment": a.get("sentiment", ""),
            "follow_up_reason": a.get("follow_up_reason", ""),
            "follow_up_date_suggestion": a.get("follow_up_date_suggestion", ""),
            "follow_up_date": fu_date.isoformat() if fu_date else None,
            "follow_up_status": doc.get("follow_up_status", "pending"),
            "summary": a.get("summary", ""),
        })
    return results


@router.get("/follow-ups/today")
async def get_follow_ups_today():
    """Get follow-ups due today or overdue."""
    now = datetime.utcnow()
    today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    results = []
    async for doc in call_logs_collection.find({
        "follow_up_status": "pending",
        "follow_up_date": {"$lte": today_end},
    }).sort("follow_up_date", 1):
        a = doc.get("analysis", {}) or {}
        results.append({
            "id": str(doc["_id"]),
            "contact_id": doc["contact_id"],
            "contact_name": doc["contact_name"],
            "phone": doc["phone"],
            "follow_up_reason": a.get("follow_up_reason", ""),
            "follow_up_date": doc.get("follow_up_date").isoformat() if doc.get("follow_up_date") else None,
            "summary": a.get("summary", ""),
        })
    return results


@router.post("/follow-ups/{call_id}/complete")
async def complete_follow_up(call_id: str):
    """Mark a follow-up as completed."""
    await call_logs_collection.update_one(
        {"_id": ObjectId(call_id)},
        {"$set": {
            "follow_up_status": "completed",
            "follow_up_completed_at": datetime.utcnow(),
        }},
    )
    return {"status": "ok"}


@router.get("/logs", response_model=list[CallLogResponse])
async def get_call_logs():
    logs = []
    async for doc in call_logs_collection.find().sort("created_at", -1).limit(50):
        # If call completed with transcript but no analysis, trigger it now -
        # capped so a persistently-failing call (e.g. insufficient_quota,
        # which never clears on retry) doesn't get re-attempted on every
        # single poll to this endpoint forever.
        existing_analysis = doc.get("analysis")
        needs_analysis = not existing_analysis or existing_analysis.get("error")
        call_id_str = str(doc["_id"])
        if (
            doc.get("status") == "completed"
            and doc.get("transcript")
            and needs_analysis
            and call_id_str not in _analysis_in_progress
            and _analysis_attempts.get(call_id_str, 0) < MAX_ANALYSIS_ATTEMPTS
        ):
            import asyncio
            _analysis_in_progress.add(call_id_str)
            _analysis_attempts[call_id_str] = _analysis_attempts.get(call_id_str, 0) + 1
            asyncio.create_task(
                _trigger_analysis(call_id_str, doc["transcript"], doc.get("contact_name", ""))
            )

        logs.append({
            "id": str(doc["_id"]),
            "contact_id": doc["contact_id"],
            "contact_name": doc["contact_name"],
            "phone": doc["phone"],
            "status": doc["status"],
            "duration": doc.get("duration", 0),
            "transcript": doc.get("transcript", ""),
            "suggestions": doc.get("suggestions", []),
            "analysis": doc.get("analysis", None),
            "created_at": doc["created_at"],
        })
    return logs


async def _trigger_analysis(call_id: str, transcript: str, contact_name: str = ""):
    """Fallback: trigger analysis for completed calls that missed it."""
    from app.services.ai_service import analyze_call
    from app.routers.ws import _parse_follow_up_date
    try:
        logger.info(f"[ANALYSIS-FALLBACK] Triggering analysis for {call_id}")
        analysis = await analyze_call(transcript, contact_name)
        update = {"analysis": analysis}
        if analysis.get("follow_up_needed"):
            update["follow_up_date"] = _parse_follow_up_date(analysis.get("follow_up_date_suggestion", ""))
            update["follow_up_status"] = "pending"
        await call_logs_collection.update_one(
            {"_id": ObjectId(call_id)},
            {"$set": update},
        )
        logger.info(f"[ANALYSIS-FALLBACK] Saved analysis for {call_id}")
    except Exception as e:
        logger.error(f"[ANALYSIS-FALLBACK] Failed for {call_id}: {e}")
    finally:
        _analysis_in_progress.discard(call_id)


@router.get("/logs/{contact_id}")
async def get_contact_call_logs(contact_id: str):
    logs = []
    async for doc in call_logs_collection.find({"contact_id": contact_id}).sort("created_at", -1):
        logs.append({
            "id": str(doc["_id"]),
            "contact_id": doc["contact_id"],
            "contact_name": doc["contact_name"],
            "phone": doc["phone"],
            "status": doc["status"],
            "duration": doc.get("duration", 0),
            "transcript": doc.get("transcript", ""),
            "suggestions": doc.get("suggestions", []),
            "analysis": doc.get("analysis", None),
            "created_at": doc["created_at"],
        })
    return logs
