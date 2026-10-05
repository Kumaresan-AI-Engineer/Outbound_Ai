import asyncio

from app.domain.calls import service
from app.domain.calls.state import ActiveCallStore


class FakeCallLogsRepo:
    """Fake in-memory repository - no real MongoDB connection needed."""

    def __init__(self):
        self.updates: list[tuple[dict, dict]] = []

    async def update_one(self, filter_: dict, update: dict):
        self.updates.append((filter_, update))


async def test_save_and_cleanup_persists_transcript_and_triggers_analysis(monkeypatch):
    store = ActiveCallStore()
    call_id = "507f1f77bcf86cd799439011"
    store.set(
        call_id,
        {
            "transcript": "[You]: Hi\n[Ravi]: Hello",
            "suggestions": [{"next_talking_point": "..."}],
            "contact_name": "Ravi",
        },
    )
    fake_repo = FakeCallLogsRepo()
    monkeypatch.setattr(service, "active_call_store", store)
    monkeypatch.setattr(service, "call_logs_repo", fake_repo)

    triggered = {}

    async def fake_run_analysis(call_id, transcript, contact_name=""):
        triggered["args"] = (call_id, transcript, contact_name)

    monkeypatch.setattr(service, "_run_analysis", fake_run_analysis)

    await service.save_and_cleanup(call_id, "completed")
    await asyncio.sleep(0)  # let the fire-and-forget analysis task run

    assert call_id not in store
    assert len(fake_repo.updates) == 1
    _filter, update = fake_repo.updates[0]
    assert update["$set"]["transcript"] == "[You]: Hi\n[Ravi]: Hello"
    assert triggered["args"][0] == call_id


async def test_save_and_cleanup_auto_schedules_followup_when_no_transcript(monkeypatch):
    store = ActiveCallStore()
    call_id = "507f1f77bcf86cd799439012"
    store.set(call_id, {"transcript": "", "suggestions": []})
    monkeypatch.setattr(service, "active_call_store", store)

    called = {}

    async def fake_auto_schedule(call_id):
        called["call_id"] = call_id

    monkeypatch.setattr(service, "auto_schedule_unanswered_followup", fake_auto_schedule)

    await service.save_and_cleanup(call_id, "failed")

    assert called["call_id"] == call_id
    assert call_id not in store


async def test_save_and_cleanup_removes_call_even_with_no_transcript_and_completed_status(monkeypatch):
    store = ActiveCallStore()
    call_id = "507f1f77bcf86cd799439013"
    store.set(call_id, {"transcript": "", "suggestions": []})
    monkeypatch.setattr(service, "active_call_store", store)

    await service.save_and_cleanup(call_id, "completed")

    assert call_id not in store
