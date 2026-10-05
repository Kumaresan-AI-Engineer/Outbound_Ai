import logging

from fastapi import HTTPException, Request, status
from twilio.request_validator import RequestValidator

from app.config import get_settings

logger = logging.getLogger(__name__)


async def verify_twilio_signature(request: Request) -> None:
    """FastAPI dependency guarding every Twilio-facing webhook.

    Twilio signs each webhook request with HMAC-SHA1 over the exact URL it called plus the
    sorted POST body params, returned as the X-Twilio-Signature header - see
    https://www.twilio.com/docs/usage/webhooks/webhooks-security. Without this check, anyone
    who finds the public webhook URL (e.g. the ngrok tunnel address) can forge call-status
    updates, inject fake transcript text, or trigger follow-up scheduling by POSTing directly
    to these endpoints - no Twilio account needed.

    The URL is reconstructed from settings.base_url (the public address Twilio actually
    called) rather than request.url, since uvicorn running behind a tunnel/reverse proxy has
    no way to know its own public scheme/host.
    """
    settings = get_settings()

    if not settings.twilio_auth_token:
        logger.warning(f"[TWILIO AUTH] Rejected {request.url.path}: TWILIO_AUTH_TOKEN is not configured")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Twilio auth not configured")

    signature = request.headers.get("X-Twilio-Signature", "")
    form = await request.form()
    params = dict(form)

    url = f"{settings.base_url.rstrip('/')}{request.url.path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"

    validator = RequestValidator(settings.twilio_auth_token)
    if not validator.validate(url, params, signature):
        logger.warning(f"[TWILIO AUTH] Rejected {request.url.path}: invalid X-Twilio-Signature")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid Twilio signature")
