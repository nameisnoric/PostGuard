from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from app.services.risk_persistence_service import (
    RiskPersistenceService,
)


class FakeResponse:
    """
    Fake requests.Response สำหรับ unit test

    ใช้แทน response จาก FastAPI จริง
    เพื่อให้ test ไม่ต้องเปิด Backend
    และไม่เขียนข้อมูลลง PostgreSQL จริง
    """

    def __init__(
        self,
        *,
        status_code: int = 200,
        payload: dict | None = None,
    ):
        self.status_code = status_code

        self._payload = (
            payload
            if payload is not None
            else {}
        )

        self.ok = (
            200
            <=
            status_code
            <
            300
        )

        self.text = str(
            self._payload
        )

    def json(self):
        return self._payload


class RiskPersistenceServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.service = (
            RiskPersistenceService()
        )

        self.session_id = 101

        self.runtime_event_id = (
            "risk-event-001"
        )

    # ========================================================
    # HELPERS
    # ========================================================

    def build_pipeline_result(
        self,
        *,
        event_action: str,
        risk_level: str = "MODERATE",
        alert_should_notify: bool = False,
        alert_type: str | None = None,
        runtime_event_id: str | None = None,
        resolved: bool = False,
    ) -> dict:
        """
        สร้าง pipeline_result จำลองให้ใกล้กับ output
        ของ ValidatedRiskPipelineService
        """

        if runtime_event_id is None:
            runtime_event_id = (
                self.runtime_event_id
            )

        event_data = {
            "runtime_event_id": (
                runtime_event_id
            ),
            "risk_level": (
                risk_level
            ),
        }

        risk_event = {
            "event_action": (
                event_action
            ),
            "current_risk_level": (
                risk_level
            ),
        }

        if resolved:
            risk_event[
                "event"
            ] = None

            risk_event[
                "resolved_event"
            ] = event_data

            risk_event[
                "reason"
            ] = (
                "RISK_RETURNED_TO_LOW"
            )

        else:
            risk_event[
                "event"
            ] = event_data

        return {
            "assessment": {
                "status": "EVALUATED",
                "reason": "TEST",

                "factors": [
                    {
                        "factor": (
                            "FLEXION"
                        ),
                    },
                    {
                        "factor": (
                            "LEFT_SHOULDER_HIGH"
                        ),
                    },
                ],
            },

            "risk": {
                "risk_level_available": (
                    True
                ),

                "risk_level": (
                    risk_level
                ),

                "evidence_groups": [
                    "NECK_SAGITTAL",
                    "LATERAL_ASYMMETRY",
                ],
            },

            "risk_event": (
                risk_event
            ),

            "alert_policy": {
                "decision": (
                    "ALERT"
                    if alert_should_notify
                    else "NO_ALERT"
                ),

                "should_notify": (
                    alert_should_notify
                ),

                "alert_type": (
                    alert_type
                ),

                "current_risk_level": (
                    risk_level
                ),

                "reason": (
                    "TEST_ALERT_POLICY"
                ),
            },
        }

    # ========================================================
    # RESET
    # ========================================================

    def test_reset_clears_runtime_mapping(
        self,
    ):
        self.service.runtime_to_database_event[
            self.runtime_event_id
        ] = 55

        self.service.reset()

        self.assertEqual(
            self.service.runtime_to_database_event,
            {},
        )

    # ========================================================
    # STARTED
    # ========================================================

    @patch(
        "app.services."
        "risk_persistence_service."
        "APIClient.create_risk_event"
    )
    def test_started_creates_risk_event(
        self,
        create_risk_event,
    ):
        create_risk_event.return_value = (
            FakeResponse(
                status_code=201,
                payload={
                    "risk_event_id": 500,
                    "session_id": (
                        self.session_id
                    ),
                    "runtime_event_id": (
                        self.runtime_event_id
                    ),
                },
            )
        )

        result = self.build_pipeline_result(
            event_action="STARTED",
            risk_level="MODERATE",
        )

        self.service.process_pipeline_result(
            session_id=self.session_id,
            pipeline_result=result,
        )

        create_risk_event.assert_called_once_with(
            session_id=(
                self.session_id
            ),

            runtime_event_id=(
                self.runtime_event_id
            ),

            risk_level="MODERATE",

            active_factors=[
                "FLEXION",
                "LEFT_SHOULDER_HIGH",
            ],

            evidence_groups=[
                "NECK_SAGITTAL",
                "LATERAL_ASYMMETRY",
            ],
        )

        self.assertEqual(
            self.service
            .runtime_to_database_event[
                self.runtime_event_id
            ],
            500,
        )

    # ========================================================
    # UPDATED
    # ========================================================

    @patch(
        "app.services."
        "risk_persistence_service."
        "APIClient.update_risk_event"
    )
    def test_updated_updates_existing_risk_event(
        self,
        update_risk_event,
    ):
        update_risk_event.return_value = (
            FakeResponse(
                status_code=200,
                payload={
                    "risk_event_id": 500,
                },
            )
        )

        result = self.build_pipeline_result(
            event_action="UPDATED",
            risk_level="MODERATE",
        )

        self.service.process_pipeline_result(
            session_id=self.session_id,
            pipeline_result=result,
        )

        update_risk_event.assert_called_once_with(
            session_id=(
                self.session_id
            ),

            runtime_event_id=(
                self.runtime_event_id
            ),

            event_action="UPDATED",

            risk_level="MODERATE",

            active_factors=[
                "FLEXION",
                "LEFT_SHOULDER_HIGH",
            ],

            evidence_groups=[
                "NECK_SAGITTAL",
                "LATERAL_ASYMMETRY",
            ],
        )

    # ========================================================
    # ESCALATED
    # ========================================================

    @patch(
        "app.services."
        "risk_persistence_service."
        "APIClient.update_risk_event"
    )
    def test_escalated_updates_same_risk_event(
        self,
        update_risk_event,
    ):
        update_risk_event.return_value = (
            FakeResponse(
                status_code=200,
                payload={
                    "risk_event_id": 500,
                },
            )
        )

        result = self.build_pipeline_result(
            event_action="ESCALATED",
            risk_level="HIGH",
        )

        self.service.process_pipeline_result(
            session_id=self.session_id,
            pipeline_result=result,
        )

        update_risk_event.assert_called_once_with(
            session_id=(
                self.session_id
            ),

            runtime_event_id=(
                self.runtime_event_id
            ),

            event_action="ESCALATED",

            risk_level="HIGH",

            active_factors=[
                "FLEXION",
                "LEFT_SHOULDER_HIGH",
            ],

            evidence_groups=[
                "NECK_SAGITTAL",
                "LATERAL_ASYMMETRY",
            ],
        )

    # ========================================================
    # DEESCALATED
    # ========================================================

    @patch(
        "app.services."
        "risk_persistence_service."
        "APIClient.update_risk_event"
    )
    def test_deescalated_updates_same_risk_event(
        self,
        update_risk_event,
    ):
        update_risk_event.return_value = (
            FakeResponse(
                status_code=200,
                payload={
                    "risk_event_id": 500,
                },
            )
        )

        result = self.build_pipeline_result(
            event_action="DEESCALATED",
            risk_level="MODERATE",
        )

        self.service.process_pipeline_result(
            session_id=self.session_id,
            pipeline_result=result,
        )

        update_risk_event.assert_called_once_with(
            session_id=(
                self.session_id
            ),

            runtime_event_id=(
                self.runtime_event_id
            ),

            event_action="DEESCALATED",

            risk_level="MODERATE",

            active_factors=[
                "FLEXION",
                "LEFT_SHOULDER_HIGH",
            ],

            evidence_groups=[
                "NECK_SAGITTAL",
                "LATERAL_ASYMMETRY",
            ],
        )

    # ========================================================
    # DATA GAP
    # ========================================================

    @patch(
        "app.services."
        "risk_persistence_service."
        "APIClient.update_risk_event"
    )
    def test_data_gap_keeps_event_active(
        self,
        update_risk_event,
    ):
        update_risk_event.return_value = (
            FakeResponse(
                status_code=200,
                payload={
                    "risk_event_id": 500,
                },
            )
        )

        result = self.build_pipeline_result(
            event_action="DATA_GAP",
            risk_level="MODERATE",
        )

        self.service.process_pipeline_result(
            session_id=self.session_id,
            pipeline_result=result,
        )

        update_risk_event.assert_called_once()

        call = (
            update_risk_event
            .call_args
            .kwargs
        )

        self.assertEqual(
            call["event_action"],
            "DATA_GAP",
        )

        self.assertEqual(
            call["runtime_event_id"],
            self.runtime_event_id,
        )

    # ========================================================
    # RESOLVED
    # ========================================================

    @patch(
        "app.services."
        "risk_persistence_service."
        "APIClient.resolve_risk_event"
    )
    def test_resolved_closes_risk_event(
        self,
        resolve_risk_event,
    ):
        resolve_risk_event.return_value = (
            FakeResponse(
                status_code=200,
                payload={
                    "risk_event_id": 500,
                    "status": "RESOLVED",
                },
            )
        )

        result = self.build_pipeline_result(
            event_action="RESOLVED",
            risk_level="MODERATE",
            resolved=True,
        )

        self.service.process_pipeline_result(
            session_id=self.session_id,
            pipeline_result=result,
        )

        resolve_risk_event.assert_called_once_with(
            session_id=(
                self.session_id
            ),

            runtime_event_id=(
                self.runtime_event_id
            ),

            resolved_reason=(
                "RISK_RETURNED_TO_LOW"
            ),
        )

    # ========================================================
    # FIRST NOTIFICATION
    # ========================================================

    @patch(
        "app.services."
        "risk_persistence_service."
        "APIClient.create_alert_notification"
    )
    @patch(
        "app.services."
        "risk_persistence_service."
        "APIClient.create_risk_event"
    )
    def test_started_with_first_alert_creates_event_and_notification(
        self,
        create_risk_event,
        create_alert_notification,
    ):
        create_risk_event.return_value = (
            FakeResponse(
                status_code=201,
                payload={
                    "risk_event_id": 500,
                },
            )
        )

        create_alert_notification.return_value = (
            FakeResponse(
                status_code=201,
                payload={
                    "notification_id": 1,
                },
            )
        )

        result = self.build_pipeline_result(
            event_action="STARTED",
            risk_level="MODERATE",
            alert_should_notify=True,
            alert_type="FIRST",
        )

        self.service.process_pipeline_result(
            session_id=self.session_id,
            pipeline_result=result,
        )

        create_risk_event.assert_called_once()

        create_alert_notification.assert_called_once_with(
            session_id=(
                self.session_id
            ),

            runtime_event_id=(
                self.runtime_event_id
            ),

            alert_type="FIRST",

            risk_level="MODERATE",

            decision="ALERT",

            reason=(
                "TEST_ALERT_POLICY"
            ),
        )

    # ========================================================
    # NO NOTIFICATION
    # ========================================================

    @patch(
        "app.services."
        "risk_persistence_service."
        "APIClient.create_alert_notification"
    )
    @patch(
        "app.services."
        "risk_persistence_service."
        "APIClient.update_risk_event"
    )
    def test_suppressed_alert_does_not_create_notification(
        self,
        update_risk_event,
        create_alert_notification,
    ):
        update_risk_event.return_value = (
            FakeResponse(
                status_code=200,
                payload={
                    "risk_event_id": 500,
                },
            )
        )

        result = self.build_pipeline_result(
            event_action="UPDATED",
            risk_level="MODERATE",
            alert_should_notify=False,
            alert_type=None,
        )

        self.service.process_pipeline_result(
            session_id=self.session_id,
            pipeline_result=result,
        )

        update_risk_event.assert_called_once()

        create_alert_notification.assert_not_called()

    # ========================================================
    # MULTIPLE NOTIFICATIONS FOR ONE RISK EVENT
    # ========================================================

    @patch(
        "app.services."
        "risk_persistence_service."
        "APIClient.create_alert_notification"
    )
    @patch(
        "app.services."
        "risk_persistence_service."
        "APIClient.update_risk_event"
    )
    @patch(
        "app.services."
        "risk_persistence_service."
        "APIClient.create_risk_event"
    )
    def test_one_risk_event_can_have_multiple_notifications(
        self,
        create_risk_event,
        update_risk_event,
        create_alert_notification,
    ):
        """
        จุดสำคัญของ architecture ใหม่:

        Risk Event = 1 episode

        Notification:
            FIRST
            REPEAT
            ESCALATION

        ต้องไม่สร้าง Risk Event ใหม่ 3 ครั้ง
        """

        create_risk_event.return_value = (
            FakeResponse(
                status_code=201,
                payload={
                    "risk_event_id": 500,
                },
            )
        )

        update_risk_event.return_value = (
            FakeResponse(
                status_code=200,
                payload={
                    "risk_event_id": 500,
                },
            )
        )

        create_alert_notification.return_value = (
            FakeResponse(
                status_code=201,
                payload={
                    "notification_id": 1,
                },
            )
        )

        # ----------------------------------------------------
        # 1. STARTED + FIRST
        # ----------------------------------------------------

        first = self.build_pipeline_result(
            event_action="STARTED",
            risk_level="MODERATE",
            alert_should_notify=True,
            alert_type="FIRST",
        )

        self.service.process_pipeline_result(
            session_id=self.session_id,
            pipeline_result=first,
        )

        # ----------------------------------------------------
        # 2. UPDATED + REPEAT
        # ----------------------------------------------------

        repeat = self.build_pipeline_result(
            event_action="UPDATED",
            risk_level="MODERATE",
            alert_should_notify=True,
            alert_type="REPEAT",
        )

        self.service.process_pipeline_result(
            session_id=self.session_id,
            pipeline_result=repeat,
        )

        # ----------------------------------------------------
        # 3. ESCALATED + ESCALATION
        # ----------------------------------------------------

        escalation = self.build_pipeline_result(
            event_action="ESCALATED",
            risk_level="HIGH",
            alert_should_notify=True,
            alert_type="ESCALATION",
        )

        self.service.process_pipeline_result(
            session_id=self.session_id,
            pipeline_result=escalation,
        )

        # Risk Event ต้องสร้างแค่ครั้งเดียว
        self.assertEqual(
            create_risk_event.call_count,
            1,
        )

        # UPDATE + ESCALATED
        self.assertEqual(
            update_risk_event.call_count,
            2,
        )

        # แต่ Notification เกิด 3 ครั้ง
        self.assertEqual(
            create_alert_notification.call_count,
            3,
        )

        notification_types = [
            call.kwargs[
                "alert_type"
            ]
            for call
            in
            create_alert_notification.call_args_list
        ]

        self.assertEqual(
            notification_types,
            [
                "FIRST",
                "REPEAT",
                "ESCALATION",
            ],
        )

        # ทั้งหมดต้องอ้างถึง runtime event เดิม
        for call in (
            create_alert_notification
            .call_args_list
        ):
            self.assertEqual(
                call.kwargs[
                    "runtime_event_id"
                ],
                self.runtime_event_id,
            )

    # ========================================================
    # INVALID SESSION
    # ========================================================

    @patch(
        "app.services."
        "risk_persistence_service."
        "APIClient.create_risk_event"
    )
    def test_invalid_session_id_does_nothing(
        self,
        create_risk_event,
    ):
        result = self.build_pipeline_result(
            event_action="STARTED",
        )

        self.service.process_pipeline_result(
            session_id=0,
            pipeline_result=result,
        )

        create_risk_event.assert_not_called()

    # ========================================================
    # API ERROR
    # ========================================================

    @patch(
        "app.services."
        "risk_persistence_service."
        "APIClient.create_risk_event"
    )
    def test_backend_error_is_raised(
        self,
        create_risk_event,
    ):
        create_risk_event.return_value = (
            FakeResponse(
                status_code=500,
                payload={
                    "detail": (
                        "Database error"
                    )
                },
            )
        )

        result = self.build_pipeline_result(
            event_action="STARTED",
        )

        with self.assertRaises(
            RuntimeError
        ):
            self.service.process_pipeline_result(
                session_id=(
                    self.session_id
                ),
                pipeline_result=result,
            )


if __name__ == "__main__":
    unittest.main()