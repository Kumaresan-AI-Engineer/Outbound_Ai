import os
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_api_key: str = ""
    twilio_api_secret: str = ""
    twilio_phone_number: str = ""
    deepgram_api_key: str = ""
    openai_api_key: str = ""
    groq_api_key: str = ""
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "outbound_calls"
    twilio_twiml_app_sid: str = ""
    whisper_model: str = "small"
    whisper_device: str = "cpu"  # "cpu" or "cuda"
    ai_provider: str = "groq"  # "groq" or "openai"
    transcription_provider: str = "deepgram"  # "deepgram" or "groq_whisper"
    suggestion_agent_enabled: bool = True
    base_url: str = "http://localhost:8080"

    class Config:
        env_file = str(BACKEND_DIR / ".env")
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
