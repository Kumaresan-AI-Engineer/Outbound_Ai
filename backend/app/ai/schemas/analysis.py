from pydantic import BaseModel, Field


class CallAnalysis(BaseModel):
    summary: str = ""
    sentiment: str = "Neutral"
    quality_score: int = 0
    went_well: list[str] = Field(default_factory=list)
    to_improve: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)
    follow_up_needed: bool = False
    follow_up_reason: str = ""
    follow_up_date_suggestion: str = ""
    key_points: list[str] = Field(default_factory=list)


class WeeklySummary(BaseModel):
    headline: str = ""
    wins: list[str] = Field(default_factory=list)
    areas_to_improve: list[str] = Field(default_factory=list)
    top_priority_action: str = ""
    outlook: str = "Neutral"
