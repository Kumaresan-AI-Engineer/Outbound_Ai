import json

from app.ai.agents import project_extraction_agent
from app.ai.providers.base import ProviderResponse
from tests.ai.agents.fakes import FakeLLMProvider


async def test_single_call_extraction_returns_validated_metadata(monkeypatch):
    canned = ProviderResponse(
        content=json.dumps(
            {
                "title": "Loan Approval Automation",
                "domain": "Banking & Finance",
                "related_domains": ["Not-A-Real-Domain"],
                "technologies": "Python",  # bare string, should be coerced to a list
                "summary": "Automated a manual loan approval workflow.",
                "key_features": ["Rules engine", "Document OCR"],
                "business_problem": "Manual review took 24 hours.",
                "solution_provided": "Automated decisioning pipeline.",
                "ai_ml_components": [],
                "tech_stack": {"backend": "FastAPI"},
                "additional_metadata": {"team_size": "5"},
            }
        )
    )
    fake = FakeLLMProvider([canned])
    monkeypatch.setattr(project_extraction_agent, "get_provider", lambda name=None: fake)

    metadata = await project_extraction_agent._single_call_extraction("full document text")

    assert metadata.title == "Loan Approval Automation"
    assert metadata.domain == "Banking & Finance"
    assert metadata.related_domains == []  # unknown domain filtered out
    assert metadata.technologies == ["Python"]  # bare string coerced to list
    assert metadata.tech_stack.backend == ["FastAPI"]
