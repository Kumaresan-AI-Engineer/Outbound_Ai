import json
import asyncio
import logging
import websockets
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

DEEPGRAM_WS_URL = "wss://api.deepgram.com/v1/listen"


class DeepgramTranscriber:
    """Real-time audio transcription via Deepgram WebSocket."""

    def __init__(self, on_transcript):
        self.on_transcript = on_transcript
        self.ws = None
        self._running = False

    async def connect(self):
        params = (
            "?encoding=mulaw"
            "&sample_rate=8000"
            "&channels=1"
            "&model=nova-2"
            "&punctuate=true"
            "&interim_results=true"
        )
        headers = {"Authorization": f"Token {settings.deepgram_api_key}"}
        try:
            self.ws = await websockets.connect(
                f"{DEEPGRAM_WS_URL}{params}",
                extra_headers=headers,
            )
            self._running = True
            asyncio.create_task(self._receive_loop())
            logger.info("[DEEPGRAM] Connected successfully")
        except Exception as e:
            logger.error(f"[DEEPGRAM] Failed to connect: {e}")
            raise

    async def _receive_loop(self):
        try:
            async for message in self.ws:
                data = json.loads(message)
                if data.get("type") == "Results":
                    transcript = (
                        data.get("channel", {})
                        .get("alternatives", [{}])[0]
                        .get("transcript", "")
                    )
                    is_final = data.get("is_final", False)
                    speech_final = data.get("speech_final", False)
                    if transcript:
                        await self.on_transcript(transcript, is_final or speech_final)
        except websockets.exceptions.ConnectionClosed:
            logger.info("[DEEPGRAM] Connection closed")
        except Exception as e:
            logger.error(f"[DEEPGRAM] Receive error: {e}")
        finally:
            self._running = False

    async def send_audio(self, audio_data: bytes):
        if self.ws and self._running:
            try:
                await self.ws.send(audio_data)
            except Exception as e:
                logger.error(f"[DEEPGRAM] Send error: {e}")

    async def close(self):
        self._running = False
        if self.ws:
            try:
                await self.ws.send(json.dumps({"type": "CloseStream"}))
                await self.ws.close()
            except Exception:
                pass
