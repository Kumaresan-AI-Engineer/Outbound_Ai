from pydantic import BaseModel, field_validator


class Suggestion(BaseModel):
    next_talking_point: str = ""
    objection_handling: str = ""
    sentiment: str = "Neutral"
    key_insight: str = ""
    recommended_project: str = ""
    clarifying_question: str = ""

    @field_validator(
        "next_talking_point",
        "objection_handling",
        "key_insight",
        "clarifying_question",
        mode="before",
    )
    @classmethod
    def _coerce_str(cls, v):
        return str(v) if v else ""

    @field_validator("sentiment", mode="before")
    @classmethod
    def _default_sentiment(cls, v):
        return v or "Neutral"

    @field_validator("recommended_project", mode="before")
    @classmethod
    def _flatten_recommended_project(cls, v):
        if isinstance(v, dict):  # tolerate {"name": ..., "pitch": ...}
            return " — ".join(str(x) for x in (v.get("name"), v.get("pitch")) if x)
        return str(v) if v else ""

    def is_actionable(self) -> bool:
        return bool(self.next_talking_point or self.objection_handling)


class ProjectSignal(BaseModel):
    is_project_inquiry: bool = False
    is_describing_own_need: bool = False
