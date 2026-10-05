import json
import asyncio
import logging
import websockets
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

DEEPGRAM_WS_URL = "wss://api.deepgram.com/v1/listen"

# Deepgram closes the socket after ~10s without audio (NET-0001). Twilio's
# outbound track is silent until the dialed party answers, so keep the
# connection alive with periodic KeepAlive messages.
KEEPALIVE_INTERVAL = 5


class DeepgramTranscriber:
    """Real-time audio transcription via Deepgram WebSocket."""

    def __init__(self, on_transcript):
        # on_transcript(text: str, is_final: bool, speech_final: bool)
        self.on_transcript = on_transcript
        self.ws = None
        self._running = False
        self._keepalive_task = None
        # TEMP DIAGNOSTIC - remove once the empty-transcript issue is root-caused
        self._frames_sent = 0
        self._bytes_sent = 0
        self._results_received = 0

    @property
    def is_running(self) -> bool:
        return self._running

    async def connect(self):
        params = (
            "?encoding=mulaw"
            "&sample_rate=8000"
            "&channels=1"
            "&model=nova-2"
            "&punctuate=true"
            "&interim_results=true"
            "&endpointing=300"
            "&utterance_end_ms=1000"
        )
        headers = {"Authorization": f"Token {settings.deepgram_api_key}"}
        try:
            self.ws = await websockets.connect(
                f"{DEEPGRAM_WS_URL}{params}",
                extra_headers=headers,
            )
            self._running = True
            asyncio.create_task(self._receive_loop())
            self._keepalive_task = asyncio.create_task(self._keepalive_loop())
            logger.info("[DEEPGRAM] Connected successfully")
        except Exception as e:
            logger.error(f"[DEEPGRAM] Failed to connect: {e}")
            raise

    async def _keepalive_loop(self):
        try:
            while self._running:
                await asyncio.sleep(KEEPALIVE_INTERVAL)
                if self.ws and self._running:
                    await self.ws.send(json.dumps({"type": "KeepAlive"}))
        except Exception:
            pass

    async def _receive_loop(self):
        try:
            async for message in self.ws:
                data = json.loads(message)
                msg_type = data.get("type")
                if msg_type == "Results":
                    transcript = (
                        data.get("channel", {})
                        .get("alternatives", [{}])[0]
                        .get("transcript", "")
                    )
                    is_final = data.get("is_final", False)
                    speech_final = data.get("speech_final", False)
                    self._results_received += 1
                    # TEMP DIAGNOSTIC - shapes only, never the spoken text itself
                    logger.info(
                        f"[DEEPGRAM-DEBUG] Results #{self._results_received}: "
                        f"is_final={is_final} speech_final={speech_final} "
                        f"text_len={len(transcript)} has_text={bool(transcript)}"
                    )
                    if transcript or speech_final:
                        await self.on_transcript(transcript, is_final, speech_final)
                elif msg_type == "UtteranceEnd":
                    logger.info("[DEEPGRAM-DEBUG] UtteranceEnd received")
                    # Safety net when speech_final never fires (noisy audio)
                    await self.on_transcript("", False, True)
                else:
                    # TEMP DIAGNOSTIC - catches error/warning/metadata messages that
                    # were previously silently dropped by this elif chain
                    logger.info(f"[DEEPGRAM-DEBUG] Unhandled message type={msg_type!r} raw={str(data)[:300]}")
        except websockets.exceptions.ConnectionClosed as e:
            logger.info(
                f"[DEEPGRAM-DEBUG] Connection closed: code={getattr(e, 'code', None)} "
                f"reason={getattr(e, 'reason', None)!r} "
                f"(frames_sent={self._frames_sent}, bytes_sent={self._bytes_sent}, results_received={self._results_received})"
            )
        except Exception as e:
            logger.error(f"[DEEPGRAM] Receive error: {e}")
        finally:
            self._running = False

    async def send_audio(self, audio_data: bytes):
        if self.ws and self._running:
            try:
                await self.ws.send(audio_data)
                # TEMP DIAGNOSTIC
                self._frames_sent += 1
                self._bytes_sent += len(audio_data)
                if self._frames_sent % 100 == 0:
                    logger.info(
                        f"[DEEPGRAM-DEBUG] Sent {self._frames_sent} frames "
                        f"({self._bytes_sent} bytes) so far, {self._results_received} Results received"
                    )
            except Exception as e:
                logger.error(f"[DEEPGRAM] Send error: {e}")
                self._running = False

    async def close(self):
        # TEMP DIAGNOSTIC - final tally for this track's connection
        logger.info(
            f"[DEEPGRAM-DEBUG] Closing: frames_sent={self._frames_sent} "
            f"bytes_sent={self._bytes_sent} results_received={self._results_received}"
        )
        self._running = False
        if self._keepalive_task:
            self._keepalive_task.cancel()
            self._keepalive_task = None
        if self.ws:
            try:
                await self.ws.send(json.dumps({"type": "CloseStream"}))
                await self.ws.close()
            except Exception:
                pass
