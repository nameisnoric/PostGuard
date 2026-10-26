"""Validated request and response contracts for risk persistence."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class PipelineRiskLevel(str, Enum):
    MODERATE = "MODERATE"
    HIGH = "HIGH"


class RiskEventStart(BaseModel):
    runtime_event_id: str = Field(min_length=1, max_length=128)
    risk_level: PipelineRiskLevel
    active_factors: list[str] = Field(default_factory=list)
    evidence_groups: list[str] = Field(default_factory=list)


class RiskEventUpdate(BaseModel):
    event_action: str = Field(min_length=1, max_length=32)
    risk_level: PipelineRiskLevel
    active_factors: list[str] = Field(default_factory=list)
    evidence_groups: list[str] = Field(default_factory=list)


class RiskEventResolve(BaseModel):
    resolved_reason: str = Field(default="RISK_EVENT_RESOLVED", max_length=128)


class AlertNotificationCreate(BaseModel):
    runtime_notification_id: str = Field(min_length=1, max_length=128)
    alert_type: str = Field(min_length=1, max_length=32)
    risk_level: PipelineRiskLevel | None = None
    decision: str = Field(default="ALERT", min_length=1, max_length=32)
    reason: str | None = Field(default=None, max_length=128)


class RiskEventResponse(BaseModel):
    risk_event_id: int
    session_id: int
    runtime_event_id: str
    initial_risk_level: str
    current_risk_level: str
    max_risk_level: str
    status: str
    started_at: datetime
    ended_at: datetime | None
    duration_seconds: float
    resolved_reason: str | None
    active_factors: list
    evidence_groups: list
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AlertNotificationResponse(BaseModel):
    notification_id: int
    risk_event_id: int
    session_id: int
    runtime_notification_id: str | None
    alert_type: str
    risk_level: str | None
    decision: str
    reason: str | None
    emitted_at: datetime
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
