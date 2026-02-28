from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Dial
from app.config import get_settings

settings = get_settings()

_twilio_client = None


def _get_client():
    global _twilio_client
    if _twilio_client is None:
        _twilio_client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    return _twilio_client


def initiate_call(to_number: str, ba_number: str, call_id: str) -> str:
    call = _get_client().calls.create(
        to=ba_number,
        from_=settings.twilio_phone_number,
        url=f"{settings.base_url}/calls/twiml/{call_id}?to_number={to_number}",
        status_callback=f"{settings.base_url}/calls/status/{call_id}",
        status_callback_event=["initiated", "ringing", "answered", "completed"],
        status_callback_method="POST",
    )
    return call.sid


def generate_twiml(call_id: str, to_number: str) -> str:
    response = VoiceResponse()

    # Stream raw audio to local Whisper via Media Streams
    ws_url = settings.base_url.replace("https://", "wss://").replace("http://", "ws://")
    start = response.start()
    start.stream(url=f"{ws_url}/calls/media-stream/{call_id}", track="both_tracks")

    response.say("Connecting you now.", voice="Polly.Joanna")

    dial = Dial(
        caller_id=settings.twilio_phone_number,
        action=f"{settings.base_url}/calls/dial-complete/{call_id}",
        method="POST",
    )
    dial.number(to_number)
    response.append(dial)

    return str(response)


def generate_twiml_for_browser(call_id: str, to_number: str) -> str:
    """Generate TwiML for browser-originated calls (Twilio Client SDK)."""
    response = VoiceResponse()

    # Stream raw audio to local Whisper via Media Streams
    ws_url = settings.base_url.replace("https://", "wss://").replace("http://", "ws://")
    start = response.start()
    start.stream(url=f"{ws_url}/calls/media-stream/{call_id}", track="both_tracks")

    dial = Dial(
        caller_id=settings.twilio_phone_number,
        action=f"{settings.base_url}/calls/dial-complete/{call_id}",
        method="POST",
    )
    dial.number(
        to_number,
        status_callback=f"{settings.base_url}/calls/status/{call_id}",
        status_callback_event="initiated ringing answered completed",
        status_callback_method="POST",
    )
    response.append(dial)

    return str(response)
