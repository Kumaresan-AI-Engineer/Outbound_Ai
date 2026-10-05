import json

from app.ai.agents import client_domain_agent
from app.ai.providers.base import ProviderResponse
from tests.ai.agents.fakes import FakeLLMProvider


async def test_classify_domain_from_text_normalizes_to_canonical_list(monkeypatch):
    canned = ProviderResponse(
        content=json.dumps(
            {
                "domain": "Banking & Finance",
                "related_domains": ["Insurance", "Not-A-Real-Domain"],
            }
        )
    )
    fake = FakeLLMProvider([canned])
    monkeypatch.setattr(client_domain_agent, "get_provider", lambda name=None: fake)

    result = await client_domain_agent._classify_domain_from_text("Client runs a regional bank.")

    assert result["domain"] == "Banking & Finance"
    assert result["related_domains"] == ["Insurance"]  # unknown domain filtered out


async def test_classify_domain_from_text_falls_back_to_other(monkeypatch):
    canned = ProviderResponse(content=json.dumps({"domain": "Not Canonical", "related_domains": []}))
    fake = FakeLLMProvider([canned])
    monkeypatch.setattr(client_domain_agent, "get_provider", lambda name=None: fake)

    result = await client_domain_agent._classify_domain_from_text("Client is ambiguous.")

    assert result["domain"] == "Other"
