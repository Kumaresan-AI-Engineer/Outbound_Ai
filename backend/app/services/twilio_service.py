from twilio.rest import Client
from twilio.twiml.voice_response import Dial, VoiceResponse

from app.config import get_settings

settings = get_settings()

_twilio_client = None


def _get_client():
    global _twilio_client
    if _twilio_client is None:
        _twilio_client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    return _twilio_client


def is_valid_caller_id(phone_number: str) -> tuple[bool, str]:
    """Check whether phone_number can legitimately be used as an outbound caller ID on this
    Twilio account, before it's added to the assignable number pool. Twilio only allows a
    Dial's caller_id to be either a number purchased/ported into the account
    (IncomingPhoneNumbers) or an external number verified via Twilio's Outgoing Caller ID
    flow - anything else gets silently rejected by Twilio at call time instead of when the
    admin adds it here.

    Returns (is_valid, reason_if_not). Raises TwilioRestException if the lookup itself fails
    (bad credentials, Twilio API unavailable) - that's a different failure mode than "this
    number isn't valid" and callers should handle it separately.
    """
    client = _get_client()
    if client.incoming_phone_numbers.list(phone_number=phone_number, limit=1):
        return True, ""
    if client.outgoing_caller_ids.list(phone_number=phone_number, limit=1):
        return True, ""
    return False, (
        "This number isn't a Twilio number on this account and isn't a verified Caller ID. "
        "Purchase/port it into Twilio, or verify it as a Caller ID in the Twilio Console, "
        "before adding it here."
    )


def initiate_call(to_number: str, ba_number: str, call_id: str, from_number: str = None) -> str:
    call = _get_client().calls.create(
        to=ba_number,
        from_=from_number or settings.twilio_phone_number,
        url=f"{settings.base_url}/calls/twiml/{call_id}?to_number={to_number}",
        status_callback=f"{settings.base_url}/calls/status/{call_id}",
        status_callback_event=["initiated", "ringing", "answered", "completed"],
        status_callback_method="POST",
    )
    return call.sid


def generate_twiml(call_id: str, to_number: str, from_number: str = None) -> str:
    response = VoiceResponse()

    # Stream raw audio to local Whisper via Media Streams
    ws_url = settings.base_url.replace("https://", "wss://").replace("http://", "ws://")
    start = response.start()
    start.stream(url=f"{ws_url}/calls/media-stream/{call_id}", track="both_tracks")

    response.say("Connecting you now.", voice="Polly.Joanna")

    dial = Dial(
        caller_id=from_number or settings.twilio_phone_number,
        action=f"{settings.base_url}/calls/dial-complete/{call_id}",
        method="POST",
    )
    dial.number(to_number)
    response.append(dial)

    return str(response)


def generate_twiml_for_browser(call_id: str, to_number: str, from_number: str = None) -> str:
    """Generate TwiML for browser-originated calls (Twilio Client SDK)."""
    response = VoiceResponse()

    # Stream raw audio to local Whisper via Media Streams
    ws_url = settings.base_url.replace("https://", "wss://").replace("http://", "ws://")
    start = response.start()
    start.stream(url=f"{ws_url}/calls/media-stream/{call_id}", track="both_tracks")

    dial = Dial(
        caller_id=from_number or settings.twilio_phone_number,
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
