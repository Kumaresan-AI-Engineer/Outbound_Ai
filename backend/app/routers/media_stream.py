import json
import base64
import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.config import get_settings
from app.routers.ws import active_calls
from app.services.whisper_service import transcribe_audio_bytes
from app.services.deepgram_service import DeepgramTranscriber
from app.services.suggestion_agent import maybe_trigger_suggestion

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/calls", tags=["media-stream"])

# Fallback (Groq Whisper) buffering: ~3 seconds of audio at 8kHz mulaw
BUFFER_SECONDS = 3
SAMPLE_RATE = 8000
BUFFER_SIZE = int(BUFFER_SECONDS * SAMPLE_RATE)

MAX_RECONNECT_ATTEMPTS = 2


def _speaker_for(call_data: dict, track: str) -> str:
    # Browser mic reaches Twilio as "inbound"; the dialed party comes back "outbound"
    return "You" if track == "inbound" else call_data.get("contact_name", "Client")


def _append_final(call_data: dict, speaker: str, text: str):
    labeled = f"[{speaker}]: {text}"
    if call_data["transcript"]:
        call_data["transcript"] += f"\n{labeled}"
    else:
        call_data["transcript"] = labeled


def _make_on_transcript(call_id: str, track: str):
    async def on_transcript(text: str, is_final: bool, speech_final: bool):
        call_data = active_calls.get(call_id)
        if not call_data:
            return
        speaker = _speaker_for(call_data, track)
        if is_final and text:
            _append_final(call_data, speaker, text)
            call_data.setdefault("interims", {}).pop(speaker, None)
            if track == "outbound":
                pending = call_data.get("agent_pending", "")
                call_data["agent_pending"] = f"{pending} {text}".strip()
        elif text:
            call_data.setdefault("interims", {})[speaker] = text
        # The contact finished an utterance -> let the agent react
        if track == "outbound" and speech_final:
            maybe_trigger_suggestion(call_id)
    return on_transcript


@router.websocket("/media-stream/{call_id}")
async def media_stream(websocket: WebSocket, call_id: str):
    """Receive Twilio Media Stream audio and transcribe it live via Deepgram
    streaming, falling back to batched Groq Whisper when unavailable."""
    await websocket.accept()

    mode = (
        "deepgram"
        if settings.transcription_provider == "deepgram" and settings.deepgram_api_key
        else "groq_whisper"
    )
    logger.info(f"[MEDIA STREAM] Connected for call {call_id} (mode={mode})")

    transcribers: dict = {}
    reconnect_attempts = {"inbound": 0, "outbound": 0}
    buffers = {"inbound": bytearray(), "outbound": bytearray()}
    transcribing = set()

    async def start_deepgram() -> bool:
        try:
            for track in ("inbound", "outbound"):
                transcribers[track] = DeepgramTranscriber(
                    on_transcript=_make_on_transcript(call_id, track)
                )
            await asyncio.gather(*(t.connect() for t in transcribers.values()))
            return True
        except Exception as e:
            logger.error(f"[MEDIA STREAM] Deepgram unavailable ({e}), falling back to Groq Whisper")
            for t in transcribers.values():
                if t.is_running:
                    await t.close()
            transcribers.clear()
            return False

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            event = msg.get("event")

            if event == "connected":
                logger.info("[MEDIA STREAM] Stream connected")

            elif event == "start":
                stream_sid = msg.get("streamSid")
                logger.info(f"[MEDIA STREAM] Stream started: sid={stream_sid}")
                if mode == "deepgram" and not await start_deepgram():
                    mode = "groq_whisper"

            elif event == "media":
                media = msg.get("media", {})
                track = media.get("track", "inbound")
                payload = media.get("payload", "")
                if not payload:
                    continue
                audio_bytes = base64.b64decode(payload)

                if mode == "deepgram":
                    t = transcribers.get(track)
                    if t and not t.is_running:
                        if reconnect_attempts[track] < MAX_RECONNECT_ATTEMPTS:
                            reconnect_attempts[track] += 1
                            logger.warning(
                                f"[MEDIA STREAM] Deepgram {track} dropped, "
                                f"reconnect attempt {reconnect_attempts[track]}"
                            )
                            try:
                                await t.connect()
                            except Exception:
                                pass
                        if t and not t.is_running and reconnect_attempts[track] >= MAX_RECONNECT_ATTEMPTS:
                            logger.error("[MEDIA STREAM] Deepgram lost, switching to Groq Whisper")
                            mode = "groq_whisper"
                    if mode == "deepgram" and t and t.is_running:
                        # Sequential send - frame ordering matters for STT
                        await t.send_audio(audio_bytes)
                        continue

                # Fallback path (also catches frames while Deepgram is down)
                buffers[track].extend(audio_bytes)
                if len(buffers[track]) >= BUFFER_SIZE and track not in transcribing:
                    audio_data = bytes(buffers[track])
                    buffers[track] = bytearray()
                    transcribing.add(track)
                    asyncio.create_task(
                        _transcribe_and_update(call_id, track, audio_data, transcribing)
                    )

            elif event == "stop":
                logger.info(f"[MEDIA STREAM] Stream stopped for call {call_id}")
                break

    except WebSocketDisconnect:
        logger.info(f"[MEDIA STREAM] Disconnected for call {call_id}")
    except Exception as e:
        logger.error(f"[MEDIA STREAM] Error for call {call_id}: {e}")
    finally:
        for t in transcribers.values():
            await t.close()
        call_data = active_calls.get(call_id)
        if call_data:
            call_data.get("interims", {}).clear()
        for track, buf in buffers.items():
            if len(buf) > SAMPLE_RATE:
                await _transcribe_and_update(call_id, track, bytes(buf), transcribing)


async def _transcribe_and_update(call_id: str, track: str, audio_bytes: bytes, transcribing: set = None):
    """Fallback path: transcribe a buffered chunk via Groq Whisper API."""
    try:
        text = await transcribe_audio_bytes(audio_bytes)
        if not text:
            return

        call_data = active_calls.get(call_id)
        if not call_data:
            return

        speaker = _speaker_for(call_data, track)
        logger.info(f"[GROQ WHISPER] track={track} -> [{speaker}] {text}")
        _append_final(call_data, speaker, text)

        if track == "outbound":
            pending = call_data.get("agent_pending", "")
            call_data["agent_pending"] = f"{pending} {text}".strip()
            maybe_trigger_suggestion(call_id)

    except Exception as e:
        logger.error(f"[GROQ WHISPER] Transcription error: {e}")
    finally:
        if transcribing is not None and track:
            transcribing.discard(track)
