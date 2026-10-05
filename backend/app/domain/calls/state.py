"""In-memory store for live call state.

Call state during an active call lives here (not in Mongo) - it's flushed to
call_logs only when the call ends (see service.save_and_cleanup). Wrapped
behind ActiveCallStore, rather than a bare module-level dict, so a later
swap to a shared backend (e.g. Redis, needed once the backend runs as more
than one worker process) only touches this file.
"""


class ActiveCallStore:
    def __init__(self) -> None:
        self._calls: dict[str, dict] = {}

    def get(self, call_id: str) -> dict | None:
        return self._calls.get(call_id)

    def set(self, call_id: str, data: dict) -> None:
        self._calls[call_id] = data

    def update(self, call_id: str, **fields) -> None:
        """Merge fields into an existing entry. No-op if the call isn't
        tracked (already ended, or never started)."""
        call = self._calls.get(call_id)
        if call is not None:
            call.update(fields)

    def pop(self, call_id: str, default: dict | None = None) -> dict | None:
        return self._calls.pop(call_id, default)

    def __contains__(self, call_id: str) -> bool:
        return call_id in self._calls


active_call_store = ActiveCallStore()
