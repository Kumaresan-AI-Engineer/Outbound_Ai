from pydantic import BaseModel, Field, field_validator, model_validator

# One canonical list shared by project classification and client matching so
# domains group consistently in queries and in the knowledge graph.
CANONICAL_DOMAINS = [
    "Healthcare",
    "Banking & Finance",
    "Insurance",
    "Retail & E-Commerce",
    "Logistics & Supply Chain",
    "Manufacturing",
    "Education",
    "Real Estate",
    "Travel & Hospitality",
    "Media & Entertainment",
    "Energy & Utilities",
    "Telecom",
    "Government",
    "HR & Recruitment",
    "Legal",
    "Other",
]


def _as_list(v) -> list[str]:
    if isinstance(v, list):
        return [str(x) for x in v if x]
    return [str(v)] if v else []


class TechStack(BaseModel):
    frontend: list[str] = Field(default_factory=list)
    backend: list[str] = Field(default_factory=list)
    database: list[str] = Field(default_factory=list)
    cloud_devops: list[str] = Field(default_factory=list)
    other: list[str] = Field(default_factory=list)

    @field_validator("frontend", "backend", "database", "cloud_devops", "other", mode="before")
    @classmethod
    def _coerce_list(cls, v):
        return _as_list(v)


class ProjectMetadata(BaseModel):
    title: str = ""
    domain: str = "Other"
    related_domains: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    summary: str = ""
    key_features: list[str] = Field(default_factory=list)
    business_problem: str = ""
    solution_provided: str = ""
    ai_ml_components: list[str] = Field(default_factory=list)
    tech_stack: TechStack = Field(default_factory=TechStack)
    additional_metadata: dict = Field(default_factory=dict)

    @field_validator("title", "summary", "business_problem", "solution_provided", mode="before")
    @classmethod
    def _coerce_str(cls, v):
        return str(v) if v else ""

    @field_validator("related_domains", "technologies", "key_features", "ai_ml_components", mode="before")
    @classmethod
    def _coerce_list(cls, v):
        return _as_list(v)

    @field_validator("tech_stack", "additional_metadata", mode="before")
    @classmethod
    def _coerce_dict(cls, v):
        return v if isinstance(v, dict) else {}

    @model_validator(mode="after")
    def _normalize_domains(self):
        if self.domain not in CANONICAL_DOMAINS:
            self.domain = "Other"
        self.related_domains = [
            d for d in self.related_domains if d in CANONICAL_DOMAINS and d != self.domain
        ]
        return self
