import json

from app.ai.agents import suggestion_agent
from app.ai.providers.base import ProviderResponse
from app.domain.calls.state import active_call_store
from tests.ai.agents.fakes import FakeLLMProvider


async def test_run_agent_once_returns_validated_suggestion(monkeypatch):
    call_id = "test-call-suggestion-1"
    active_call_store.set(
        call_id,
        {
            "transcript": (
                "[You]: Hi Ravi, thanks for taking the time today.\n"
                "[Ravi]: Our loan approvals take almost 24 hours right now."
            ),
            "contact_name": "Ravi",
            "agent_cache": {"contact_profile": {}, "relevant_projects": None},
            "started_at": None,
        },
    )
    try:
        signal_response = ProviderResponse(
            content=json.dumps({"is_project_inquiry": False, "is_describing_own_need": False})
        )
        suggestion_response = ProviderResponse(
            content=json.dumps(
                {
                    "next_talking_point": "Ask what's driving the push to speed up approvals.",
                    "objection_handling": "",
                    "sentiment": "Neutral",
                    "key_insight": "Loan approvals take 24 hours today.",
                    "recommended_project": "",
                    "clarifying_question": "",
                }
            )
        )
        fake = FakeLLMProvider([signal_response, suggestion_response])
        monkeypatch.setattr(suggestion_agent, "get_provider", lambda name=None: fake)

        result = await suggestion_agent._run_agent_once(call_id)

        assert result["next_talking_point"] == "Ask what's driving the push to speed up approvals."
        assert result["sentiment"] == "Neutral"
        assert fake.calls[-1]["model"] == suggestion_agent.MODEL
    finally:
        active_call_store.pop(call_id, None)


async def test_run_agent_once_returns_none_when_suggestion_is_empty(monkeypatch):
    call_id = "test-call-suggestion-2"
    active_call_store.set(
        call_id,
        {
            "transcript": "[You]: Hello\n[Ravi]: Hi.",
            "contact_name": "Ravi",
            "agent_cache": {"contact_profile": {}, "relevant_projects": None},
            "started_at": None,
        },
    )
    try:
        signal_response = ProviderResponse(
            content=json.dumps({"is_project_inquiry": False, "is_describing_own_need": False})
        )
        empty_suggestion = ProviderResponse(
            content=json.dumps(
                {
                    "next_talking_point": "",
                    "objection_handling": "",
                    "sentiment": "Neutral",
                    "key_insight": "",
                    "recommended_project": "",
                    "clarifying_question": "",
                }
            )
        )
        fake = FakeLLMProvider([signal_response, empty_suggestion])
        monkeypatch.setattr(suggestion_agent, "get_provider", lambda name=None: fake)

        result = await suggestion_agent._run_agent_once(call_id)

        assert result is None
    finally:
        active_call_store.pop(call_id, None)
