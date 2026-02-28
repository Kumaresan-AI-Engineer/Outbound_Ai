import logging
import audioop
import io
import httpx
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

GROQ_WHISPER_URL = "https://api.groq.com/openai/v1/audio/transcriptions"


async def transcribe_audio_bytes(mulaw_bytes: bytes) -> str:
    """Convert mulaw to WAV and transcribe via Groq Whisper API."""
    if len(mulaw_bytes) == 0:
        return ""

    # Convert mulaw 8kHz to 16-bit PCM 16kHz
    pcm_16bit = audioop.ulaw2lin(mulaw_bytes, 2)
    pcm_16bit, _ = audioop.ratecv(pcm_16bit, 2, 1, 8000, 16000, None)

    # Check if audio is too quiet (silence)
    import numpy as np
    samples = np.frombuffer(pcm_16bit, dtype=np.int16).astype(np.float32) / 32768.0
    rms = float(np.sqrt(np.mean(samples ** 2)))
    if rms < 0.005:
        return ""

    # Build WAV file in memory
    wav_buf = io.BytesIO()
    import wave
    with wave.open(wav_buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(pcm_16bit)
    wav_buf.seek(0)

    # Send to Groq Whisper API
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            GROQ_WHISPER_URL,
            headers={"Authorization": f"Bearer {settings.groq_api_key}"},
            files={"file": ("audio.wav", wav_buf, "audio/wav")},
            data={"model": "whisper-large-v3", "language": "en", "response_format": "text"},
        )
        if resp.status_code != 200:
            logger.error(f"[GROQ WHISPER] API error {resp.status_code}: {resp.text}")
            return ""
        text = resp.text.strip()
        return text
