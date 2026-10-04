from pydantic import BaseModel, ConfigDict

class SessionSummaryCreate(BaseModel):
    average_risk_score: float = 0.0
    maximum_risk_score: float = 0.0
    blink_rate: float | None = None

class SessionSummaryResponse(BaseModel):
    summary_id: int
    session_id: int

    average_risk_score: float
    maximum_risk_score: float

    low_risk_duration: int
    medium_risk_duration: int
    high_risk_duration: int

    low_risk_alert_count: int
    medium_risk_alert_count: int
    high_risk_alert_count: int

    total_alert_count: int

    most_frequent_alert_event: str | None

    blink_rate: float | None

    model_config = ConfigDict(from_attributes=True)