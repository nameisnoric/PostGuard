from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


RiskLevel = Literal[
    "MODERATE",
    "HIGH",
]

RiskEventAction = Literal[
    "STARTED",
    "UPDATED",
    "ESCALATED",
    "DEESCALATED",
    "RESOLVED",
    "DATA_GAP",
]

AlertType = Literal[
    "FIRST",
    "REPEAT",
    "ESCALATION",
    "RESOLUTION",
]


class RiskEventStart(BaseModel):
    runtime_event_id: str = Field(
        min_length=1,
        max_length=128,
    )

    risk_level: RiskLevel

    active_factors: list[str] = Field(
        default_factory=list
    )

    evidence_groups: list[str] = Field(
        default_factory=list
    )


class RiskEventUpdate(BaseModel):
    event_action: RiskEventAction

    risk_level: RiskLevel

    active_factors: list[str] = Field(
        default_factory=list
    )

    evidence_groups: list[str] = Field(
        default_factory=list
    )


class RiskEventResolve(BaseModel):
    resolved_reason: str = Field(
        default="RISK_EVENT_RESOLVED",
        min_length=1,
        max_length=128,
    )


class AlertNotificationCreate(BaseModel):
    alert_type: AlertType

    risk_level: RiskLevel | None = None

    decision: str = Field(
        default="ALERT",
        min_length=1,
        max_length=32,
    )

    reason: str | None = Field(
        default=None,
        max_length=128,
    )


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

    model_config = ConfigDict(
        from_attributes=True
    )


class AlertNotificationResponse(BaseModel):
    notification_id: int

    risk_event_id: int
    session_id: int

    alert_type: str
    risk_level: str | None

    decision: str
    reason: str | None

    emitted_at: datetime
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )