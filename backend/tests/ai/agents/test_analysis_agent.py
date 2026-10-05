import json

from app.ai.agents import analysis_agent
from app.ai.providers.base import ProviderResponse
from tests.ai.agents.fakes import FakeLLMProvider


async def test_analyze_call_returns_validated_shape(monkeypatch):
    canned = ProviderResponse(
        content=json.dumps(
            {
                "summary": "Great call with Ravi.",
                "sentiment": "Positive",
                "quality_score": 8,
                "went_well": ["Built rapport"],
                "to_improve": [],
                "action_items": ["Send proposal"],
                "follow_up_needed": True,
                "follow_up_reason": "Wants a proposal",
                "follow_up_date_suggestion": "in 2 days",
                "key_points": ["Budget confirmed"],
            }
        )
    )
    fake = FakeLLMProvider([canned])
    monkeypatch.setattr(analysis_agent, "get_provider", lambda name=None: fake)

    result = await analysis_agent.analyze_call("transcript text", "Ravi")

    assert result["summary"] == "Great call with Ravi."
    assert result["sentiment"] == "Positive"
    assert result["quality_score"] == 8
    assert result["follow_up_needed"] is True
    assert fake.calls[0]["model"]  # model name was resolved and passed through


async def test_analyze_call_falls_back_on_bad_json(monkeypatch):
    bad = ProviderResponse(content="not json")
    fake = FakeLLMProvider([bad, bad])  # complete_structured retries once
    monkeypatch.setattr(analysis_agent, "get_provider", lambda name=None: fake)

    result = await analysis_agent.analyze_call("transcript text")

    assert "error" in result
    assert result["summary"] == "Analysis failed."


async def test_generate_weekly_summary_returns_validated_shape(monkeypatch):
    canned = ProviderResponse(
        content=json.dumps(
            {
                "headline": "Strong week overall.",
                "wins": ["Two demos booked"],
                "areas_to_improve": ["Follow up faster"],
                "top_priority_action": "Call back warm leads",
                "outlook": "Positive",
            }
        )
    )
    fake = FakeLLMProvider([canned])
    monkeypatch.setattr(analysis_agent, "get_provider", lambda name=None: fake)

    result = await analysis_agent.generate_weekly_summary("digest text", 12)

    assert result["headline"] == "Strong week overall."
    assert result["outlook"] == "Positive"
