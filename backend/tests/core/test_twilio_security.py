import pytest
from fastapi import HTTPException
from starlette.requests import Request
from twilio.request_validator import RequestValidator

from app.config import get_settings
from app.core.twilio_security import verify_twilio_signature

BASE_URL = "https://example.ngrok-free.dev"
AUTH_TOKEN = "test_auth_token"
PATH = "/calls/status/abc123"
PARAMS = {"CallStatus": "completed", "CallSid": "CA123"}


def _make_request(path: str, params: dict, signature: str, query: str = "") -> Request:
    body = "&".join(f"{k}={v}" for k, v in params.items()).encode()
    scope = {
        "type": "http",
        "method": "POST",
        "path": path,
        "query_string": query.encode(),
        "headers": [
            (b"x-twilio-signature", signature.encode()),
            (b"content-type", b"application/x-www-form-urlencoded"),
        ],
    }

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(scope, receive)


@pytest.fixture(autouse=True)
def _configured_settings(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "base_url", BASE_URL)
    monkeypatch.setattr(settings, "twilio_auth_token", AUTH_TOKEN)
    return settings


async def test_valid_signature_is_accepted():
    signature = RequestValidator(AUTH_TOKEN).compute_signature(f"{BASE_URL}{PATH}", PARAMS)
    request = _make_request(PATH, PARAMS, signature)

    await verify_twilio_signature(request)  # does not raise


async def test_tampered_params_are_rejected():
    signature = RequestValidator(AUTH_TOKEN).compute_signature(f"{BASE_URL}{PATH}", PARAMS)
    tampered_params = {**PARAMS, "CallStatus": "failed"}
    request = _make_request(PATH, tampered_params, signature)

    with pytest.raises(HTTPException) as exc_info:
        await verify_twilio_signature(request)
    assert exc_info.value.status_code == 403


async def test_wrong_auth_token_is_rejected():
    signature = RequestValidator("a-different-token").compute_signature(f"{BASE_URL}{PATH}", PARAMS)
    request = _make_request(PATH, PARAMS, signature)

    with pytest.raises(HTTPException) as exc_info:
        await verify_twilio_signature(request)
    assert exc_info.value.status_code == 403


async def test_missing_signature_header_is_rejected():
    request = _make_request(PATH, PARAMS, signature="")

    with pytest.raises(HTTPException) as exc_info:
        await verify_twilio_signature(request)
    assert exc_info.value.status_code == 403


async def test_query_string_is_part_of_the_signed_url():
    # Signed for ?to_number=+15551234567 - a request that changes the query
    # string (or drops it) must fail even with an otherwise-valid signature.
    signed_url = f"{BASE_URL}{PATH}?to_number=%2B15551234567"
    signature = RequestValidator(AUTH_TOKEN).compute_signature(signed_url, PARAMS)

    matching_request = _make_request(PATH, PARAMS, signature, query="to_number=%2B15551234567")
    await verify_twilio_signature(matching_request)  # does not raise

    mismatched_request = _make_request(PATH, PARAMS, signature, query="to_number=%2B19999999999")
    with pytest.raises(HTTPException) as exc_info:
        await verify_twilio_signature(mismatched_request)
    assert exc_info.value.status_code == 403


async def test_missing_auth_token_rejects_everything(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "twilio_auth_token", "")
    request = _make_request(PATH, PARAMS, signature="anything")

    with pytest.raises(HTTPException) as exc_info:
        await verify_twilio_signature(request)
    assert exc_info.value.status_code == 403
