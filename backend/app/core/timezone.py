"""Convert stored UTC datetimes to the requesting client's timezone for display.

Everything is stored in Mongo as naive UTC (datetime.utcnow()) - that doesn't
change. This module only affects what API responses send back: the frontend
sends its IANA timezone name (e.g. "Asia/Kolkata") on the X-Timezone header of
every request (see frontend/src/services/apiClient.js), and list/get endpoints
convert each outgoing datetime into that zone before serializing. A missing or
invalid header falls back to UTC untouched.
"""

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Request

DEFAULT_TZ = "UTC"


def get_request_timezone(request: Request) -> str:
    """FastAPI dependency - validated IANA timezone name for this request."""
    tz_name = request.headers.get("X-Timezone", DEFAULT_TZ)
    try:
        ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        return DEFAULT_TZ
    return tz_name


def to_tz(dt: datetime | None, tz_name: str) -> datetime | None:
    """Reinterpret a stored (naive UTC) datetime in tz_name. Already tz-aware
    datetimes are converted as-is rather than assumed to be UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(ZoneInfo(tz_name))
