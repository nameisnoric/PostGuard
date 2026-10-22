from __future__ import annotations

from app.services.api_client import APIClient


class RiskPersistenceService:
    """
    Persist validated PostGuard Risk Event / Alert Policy output.

    This service does not calculate risk.
    It only maps validated runtime output to Backend persistence API.
    """

    def __init__(self) -> None:
        self.runtime_to_database_event: dict[str, int] = {}

    def reset(self) -> None:
        """
        Clear Desktop-side runtime mapping.

        Called when starting a new Session or when the Session ends.
        """
        self.runtime_to_database_event.clear()

    @staticmethod
    def _factor_names(
        assessment: dict,
    ) -> list[str]:
        factors = (
            assessment.get("factors")
            or []
        )

        result: list[str] = []

        for factor in factors:
            if not isinstance(
                factor,
                dict,
            ):
                continue

            name = factor.get(
                "factor"
            )

            if isinstance(
                name,
                str,
            ):
                result.append(
                    name
                )

        return result

    @staticmethod
    def _evidence_groups(
        risk: dict,
    ) -> list[str]:
        groups = (
            risk.get(
                "evidence_groups"
            )
            or []
        )

        result: list[str] = []

        for group in groups:
            if isinstance(
                group,
                str,
            ):
                result.append(
                    group
                )

            elif isinstance(
                group,
                dict,
            ):
                name = (
                    group.get("group")
                    or
                    group.get("name")
                    or
                    group.get(
                        "evidence_group"
                    )
                )

                if isinstance(
                    name,
                    str,
                ):
                    result.append(
                        name
                    )

        return result

    @staticmethod
    def _extract_runtime_event_id(
        risk_event: dict,
    ) -> str | None:
        event = risk_event.get(
            "event"
        )

        if isinstance(
            event,
            dict,
        ):
            event_id = event.get(
                "runtime_event_id"
            )

            if event_id is not None:
                return str(
                    event_id
                )

        resolved_event = risk_event.get(
            "resolved_event"
        )

        if isinstance(
            resolved_event,
            dict,
        ):
            event_id = (
                resolved_event.get(
                    "runtime_event_id"
                )
            )

            if event_id is not None:
                return str(
                    event_id
                )

        return None

    @staticmethod
    def _require_success(
        response,
        operation: str,
    ) -> dict:
        if not response.ok:
            try:
                payload = response.json()
            except ValueError:
                payload = response.text

            raise RuntimeError(
                f"{operation} failed: "
                f"HTTP {response.status_code} "
                f"{payload}"
            )

        data = response.json()

        if not isinstance(
            data,
            dict,
        ):
            raise RuntimeError(
                f"{operation} returned invalid JSON."
            )

        return data

    def process_pipeline_result(
        self,
        *,
        session_id: int,
        pipeline_result: dict,
    ) -> None:
        """
        Persist one validated pipeline output.

        Mapping:
        STARTED
            -> create Risk Event

        UPDATED / ESCALATED / DEESCALATED / DATA_GAP
            -> update Risk Event

        RESOLVED
            -> resolve Risk Event

        should_notify=True
            -> create Alert Notification
        """

        if (
            type(session_id)
            is not int
            or
            session_id <= 0
        ):
            return

        risk_event = (
            pipeline_result.get(
                "risk_event"
            )
            or {}
        )

        alert_policy = (
            pipeline_result.get(
                "alert_policy"
            )
            or {}
        )

        assessment = (
            pipeline_result.get(
                "assessment"
            )
            or {}
        )

        risk = (
            pipeline_result.get(
                "risk"
            )
            or {}
        )

        event_action = (
            risk_event.get(
                "event_action"
            )
        )

        runtime_event_id = (
            self._extract_runtime_event_id(
                risk_event
            )
        )

        current_risk_level = (
            risk_event.get(
                "current_risk_level"
            )
            or
            risk.get(
                "risk_level"
            )
        )

        active_factors = (
            self._factor_names(
                assessment
            )
        )

        evidence_groups = (
            self._evidence_groups(
                risk
            )
        )

        # ----------------------------------------------------
        # Risk Event START
        # ----------------------------------------------------

        if (
            event_action == "STARTED"
            and
            runtime_event_id is not None
            and
            current_risk_level
            in ("MODERATE", "HIGH")
        ):
            response = (
                APIClient.create_risk_event(
                    session_id=session_id,
                    runtime_event_id=(
                        runtime_event_id
                    ),
                    risk_level=(
                        current_risk_level
                    ),
                    active_factors=(
                        active_factors
                    ),
                    evidence_groups=(
                        evidence_groups
                    ),
                )
            )

            data = self._require_success(
                response,
                "Create risk event",
            )

            risk_event_id = (
                data.get(
                    "risk_event_id"
                )
            )

            if type(risk_event_id) is int:
                self.runtime_to_database_event[
                    runtime_event_id
                ] = risk_event_id

        # ----------------------------------------------------
        # Risk Event UPDATE
        # ----------------------------------------------------

        elif (
            event_action
            in (
                "UPDATED",
                "ESCALATED",
                "DEESCALATED",
                "DATA_GAP",
            )
            and
            runtime_event_id is not None
            and
            current_risk_level
            in ("MODERATE", "HIGH")
        ):
            response = (
                APIClient.update_risk_event(
                    session_id=session_id,
                    runtime_event_id=(
                        runtime_event_id
                    ),
                    event_action=(
                        event_action
                    ),
                    risk_level=(
                        current_risk_level
                    ),
                    active_factors=(
                        active_factors
                    ),
                    evidence_groups=(
                        evidence_groups
                    ),
                )
            )

            self._require_success(
                response,
                "Update risk event",
            )

        # ----------------------------------------------------
        # Risk Event RESOLVE
        # ----------------------------------------------------

        elif (
            event_action == "RESOLVED"
            and
            runtime_event_id is not None
        ):
            response = (
                APIClient.resolve_risk_event(
                    session_id=session_id,
                    runtime_event_id=(
                        runtime_event_id
                    ),
                    resolved_reason=(
                        risk_event.get(
                            "reason"
                        )
                        or
                        "RISK_EVENT_RESOLVED"
                    ),
                )
            )

            self._require_success(
                response,
                "Resolve risk event",
            )

        # ----------------------------------------------------
        # Alert Notification
        # ----------------------------------------------------

        should_notify = (
            alert_policy.get(
                "should_notify"
            )
            is True
        )

        if (
            should_notify
            and
            runtime_event_id is not None
        ):
            alert_type = (
                alert_policy.get(
                    "alert_type"
                )
            )

            if alert_type in (
                "FIRST",
                "REPEAT",
                "ESCALATION",
            ):
                response = (
                    APIClient.create_alert_notification(
                        session_id=session_id,
                        runtime_event_id=(
                            runtime_event_id
                        ),
                        alert_type=(
                            alert_type
                        ),
                        risk_level=(
                            alert_policy.get(
                                "current_risk_level"
                            )
                        ),
                        decision=(
                            alert_policy.get(
                                "decision"
                            )
                            or
                            "ALERT"
                        ),
                        reason=(
                            alert_policy.get(
                                "reason"
                            )
                        ),
                    )
                )

                self._require_success(
                    response,
                    "Create alert notification",
                )