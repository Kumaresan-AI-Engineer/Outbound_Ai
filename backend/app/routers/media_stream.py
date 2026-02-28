import json
import base64
import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.routers.ws import active_calls
from app.services.whisper_service import transcribe_audio_bytes

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/calls", tags=["media-stream"])

# Buffer ~3 seconds of audio at 8kHz mulaw (1 byte per sample)
BUFFER_SECONDS = 3
SAMPLE_RATE = 8000
BUFFER_SIZE = int(BUFFER_SECONDS * SAMPLE_RATE)


@router.websocket("/media-stream/{call_id}")
async def media_stream(websocket: WebSocket, call_id: str):
    """Receive Twilio Media Stream WebSocket, buffer audio, transcribe with Groq Whisper."""
    await websocket.accept()
    logger.info(f"[MEDIA STREAM] Connected for call {call_id}")

    buffers = {"inbound": bytearray(), "outbound": bytearray()}
    transcribing = set()
    stream_sid = None

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            event = msg.get("event")

            if event == "connected":
                logger.info(f"[MEDIA STREAM] Stream connected")

            elif event == "start":
                stream_sid = msg.get("streamSid")
                logger.info(f"[MEDIA STREAM] Stream started: sid={stream_sid}")

            elif event == "media":
                media = msg.get("media", {})
                track = media.get("track", "inbound")
                payload = media.get("payload", "")
                if payload:
                    audio_bytes = base64.b64decode(payload)
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
                for track, buf in buffers.items():
                    if len(buf) > SAMPLE_RATE:
                        asyncio.create_task(
                            _transcribe_and_update(call_id, track, bytes(buf), transcribing)
                        )
                break

    except WebSocketDisconnect:
        logger.info(f"[MEDIA STREAM] Disconnected for call {call_id}")
    except Exception as e:
        logger.error(f"[MEDIA STREAM] Error for call {call_id}: {e}")
    finally:
        for track, buf in buffers.items():
            if len(buf) > SAMPLE_RATE:
                await _transcribe_and_update(call_id, track, bytes(buf), transcribing)


async def _transcribe_and_update(call_id: str, track: str, audio_bytes: bytes, transcribing: set = None):
    """Transcribe via Groq API and update active_calls."""
    try:
        text = await transcribe_audio_bytes(audio_bytes)

        if not text:
            return

        call_data = active_calls.get(call_id)
        if not call_data:
            return

        contact_name = call_data.get("contact_name", "Client")
        speaker = contact_name if track == "inbound" else "You"

        logger.info(f"[GROQ WHISPER] [{speaker}] {text}")

        labeled = f"[{speaker}]: {text}"
        if call_data["transcript"]:
            call_data["transcript"] += f"\n{labeled}"
        else:
            call_data["transcript"] = labeled

    except Exception as e:
        logger.error(f"[GROQ WHISPER] Transcription error: {e}")
    finally:
        if transcribing and track:
            transcribing.discard(track)
