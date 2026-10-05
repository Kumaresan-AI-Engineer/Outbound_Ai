from pydantic import BaseModel, Field, field_validator, model_validator

from app.ai.schemas.project_extraction import CANONICAL_DOMAINS


class DomainClassification(BaseModel):
    domain: str = "Other"
    related_domains: list[str] = Field(default_factory=list)

    @field_validator("related_domains", mode="before")
    @classmethod
    def _coerce_list(cls, v):
        if isinstance(v, list):
            return [str(x) for x in v if x]
        return [str(v)] if v else []

    @model_validator(mode="after")
    def _normalize_domains(self):
        if self.domain not in CANONICAL_DOMAINS:
            self.domain = "Other"
        self.related_domains = [
            d for d in self.related_domains if d in CANONICAL_DOMAINS and d != self.domain
        ]
        return self
