"""Session Summary API integration tests against an isolated in-memory database."""

import os
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

# ============================================================
# TEST DATABASE SAFETY
# ============================================================

# Must be set before importing the application database.
# Never use the configured PostGuard PostgreSQL database here.
os.environ["DATABASE_URL"] = "sqlite://"

from fastapi import FastAPI
from fastapi.testclient import TestClient

from sqlalchemy import (
    create_engine,
    func,
    select,
)
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.database import (
    Base,
    get_db,
)

# Import all models so SQLAlchemy knows all tables.
import app.models

from app.models.alert_notification import AlertNotification
from app.models.camera import Camera
from app.models.personal_baseline import PersonalBaseline
from app.models.risk_event_record import RiskEventRecord
from app.models.session import PostureSession
from app.models.session_summary import SessionSummary
from app.models.user import User

from app.routers.auth import get_current_user
from app.routers.session_summaries import router

from app.schemas.session_summary import SessionSummaryCreate


class SessionSummaryTests(unittest.TestCase):

    # ========================================================
    # SETUP
    # ========================================================

    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={
                "check_same_thread": False,
            },
            poolclass=StaticPool,
        )

        Base.metadata.create_all(
            self.engine
        )

        self.db = Session(
            self.engine
        )

        # ----------------------------------------------------
        # User
        # ----------------------------------------------------

        self.db.add(
            User(
                id=1,
                email="summary@example.invalid",
                username="summary",
                password_hash="test",
            )
        )

        self.db.flush()

        # ----------------------------------------------------
        # Camera
        # ----------------------------------------------------

        self.db.add(
            Camera(
                camera_id=1,
                user_id=1,
                device_id="test",
                camera_name="test",
                resolution_width=640,
                resolution_height=360,
            )
        )

        self.db.flush()

        # ----------------------------------------------------
        # Personal Baseline
        # ----------------------------------------------------

        self.db.add(
            PersonalBaseline(
                baseline_id=1,
                user_id=1,
                camera_id=1,

                camera_frame_width=640,
                camera_frame_height=360,

                camera_scale_x=3.5,
                camera_scale_y=3.5,
                camera_scale_avg=3.5,

                camera_card_roll=0.0,

                camera_horizontal_perspective=0.0,
                camera_vertical_perspective=0.0,

                camera_calibrated_at=datetime.now(
                    timezone.utc
                ),

                baseline_status="SUCCESS",
                confirmation_status="CONFIRMED",

                baseline_sample_count=60,
                baseline_duration_seconds=15.0,
                baseline_valid_ratio=1.0,

                shoulder_angle=-1.25,
                lateral_tilt_baseline=2.75,
                neck_flexion_baseline=1.5,

                ipd_baseline=70.0,
            )
        )

        self.db.flush()

        # ----------------------------------------------------
        # Completed Session
        # ----------------------------------------------------

        self.db.add(
            PostureSession(
                session_id=1,
                user_id=1,
                camera_id=1,
                baseline_id=1,
                status="COMPLETED",
            )
        )

        self.db.commit()

        # ----------------------------------------------------
        # FastAPI test app
        # ----------------------------------------------------

        self.app = FastAPI()

        self.app.include_router(
            router
        )

        self.app.dependency_overrides[
            get_db
        ] = lambda: self.db

        self.app.dependency_overrides[
            get_current_user
        ] = lambda: SimpleNamespace(
            id=1
        )

        self.client = TestClient(
            self.app
        )

        # ----------------------------------------------------
        # Session Summary payload
        # ----------------------------------------------------

        self.payload = {
            "detection_count": 20,
            "pose_detected_count": 18,
            "face_detected_count": 15,
            "average_shoulder": -1.25,
            "average_neck": 2.75,
        }

    # ========================================================
    # TEARDOWN
    # ========================================================

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()

    # ========================================================
    # HELPERS
    # ========================================================

    def create_moderate_risk_event(
        self,
        duration_seconds=12.0,
    ):
        """
        Create one resolved MODERATE Risk Event.

        This replaces legacy AlertEvent.
        """

        started_at = datetime.now(
            timezone.utc
        )

        ended_at = (
            started_at
            + timedelta(
                seconds=duration_seconds
            )
        )

        event = RiskEventRecord(
            session_id=1,

            runtime_event_id="test-runtime-event-1",

            initial_risk_level="MODERATE",
            current_risk_level="MODERATE",
            max_risk_level="MODERATE",

            status="RESOLVED",

            started_at=started_at,
            ended_at=ended_at,

            duration_seconds=duration_seconds,

            resolved_reason="RISK_RETURNED_TO_LOW",

            active_factors=[
                "TILT_LEFT",
            ],

            evidence_groups=[
                "LATERAL_ASYMMETRY",
            ],
        )

        self.db.add(
            event
        )

        self.db.flush()

        return event

    def create_notification(
        self,
        event,
        *,
        alert_type="FIRST",
        risk_level="MODERATE",
    ):
        """
        Create one notification belonging to Risk Event.
        """

        notification = AlertNotification(
            risk_event_id=event.risk_event_id,
            session_id=1,

            alert_type=alert_type,
            risk_level=risk_level,

            decision="NOTIFY",

            reason="ALERT_POLICY_NOTIFY",

            emitted_at=datetime.now(
                timezone.utc
            ),
        )

        self.db.add(
            notification
        )

        self.db.flush()

        return notification

    # ========================================================
    # SAVE + READ + DUPLICATE
    # ========================================================

    def test_save_read_and_duplicate(self):

        # ----------------------------------------------------
        # Create new validated persistence records
        # ----------------------------------------------------

        event = self.create_moderate_risk_event(
            duration_seconds=12.0
        )

        self.create_notification(
            event,
            alert_type="FIRST",
            risk_level="MODERATE",
        )

        self.db.commit()

        # ----------------------------------------------------
        # Create Summary
        # ----------------------------------------------------

        result = self.client.post(
            "/sessions/1/summary",
            json=self.payload,
        )

        self.assertEqual(
            result.status_code,
            201,
            result.text,
        )

        self.db.expire_all()

        # ----------------------------------------------------
        # Read Summary
        # ----------------------------------------------------

        response = self.client.get(
            "/sessions/1/summary"
        )

        self.assertEqual(
            response.status_code,
            200,
            response.text,
        )

        saved = response.json()

        # ----------------------------------------------------
        # Detection Summary must still be preserved
        # ----------------------------------------------------

        for key, value in self.payload.items():
            self.assertEqual(
                saved[key],
                value,
                f"{key} was not persisted correctly",
            )

        # ----------------------------------------------------
        # Modified RULA not implemented yet
        # ----------------------------------------------------

        self.assertIsNone(
            saved[
                "average_risk_score"
            ]
        )

        self.assertIsNone(
            saved[
                "maximum_risk_score"
            ]
        )

        # ----------------------------------------------------
        # Risk Event duration
        #
        # MODERATE temporarily maps to medium_risk_*
        # because existing DB schema still uses that name.
        # ----------------------------------------------------

        self.assertEqual(
            saved[
                "low_risk_duration"
            ],
            0,
        )

        self.assertEqual(
            saved[
                "medium_risk_duration"
            ],
            12,
        )

        self.assertEqual(
            saved[
                "high_risk_duration"
            ],
            0,
        )

        # ----------------------------------------------------
        # Notification count
        # ----------------------------------------------------

        self.assertEqual(
            saved[
                "low_risk_alert_count"
            ],
            0,
        )

        self.assertEqual(
            saved[
                "medium_risk_alert_count"
            ],
            1,
        )

        self.assertEqual(
            saved[
                "high_risk_alert_count"
            ],
            0,
        )

        self.assertEqual(
            saved[
                "total_alert_count"
            ],
            1,
        )

        self.assertEqual(
            saved[
                "most_frequent_alert_event"
            ],
            "FIRST",
        )

        # ----------------------------------------------------
        # List summaries
        # ----------------------------------------------------

        all_response = self.client.get(
            "/summaries"
        )

        self.assertEqual(
            all_response.status_code,
            200,
            all_response.text,
        )

        self.assertEqual(
            all_response.json(),
            [saved],
        )

        # ----------------------------------------------------
        # Duplicate Summary must be rejected
        # ----------------------------------------------------

        duplicate = self.client.post(
            "/sessions/1/summary",
            json=self.payload,
        )

        self.assertEqual(
            duplicate.status_code,
            409,
        )

        count = self.db.scalar(
            select(
                func.count()
            )
            .select_from(
                SessionSummary
            )
        )

        self.assertEqual(
            count,
            1,
        )

    # ========================================================
    # ONE EVENT -> MULTIPLE NOTIFICATIONS
    # ========================================================

    def test_one_risk_event_can_have_multiple_notifications(
        self,
    ):
        """
        Risk Event count and notification count are intentionally
        different concepts.
        """

        event = self.create_moderate_risk_event(
            duration_seconds=30.0
        )

        self.create_notification(
            event,
            alert_type="FIRST",
        )

        self.create_notification(
            event,
            alert_type="REPEAT",
        )

        self.create_notification(
            event,
            alert_type="REPEAT",
        )

        self.db.commit()

        result = self.client.post(
            "/sessions/1/summary",
            json=self.payload,
        )

        self.assertEqual(
            result.status_code,
            201,
            result.text,
        )

        saved = result.json()

        # One risk episode lasted 30 seconds.
        self.assertEqual(
            saved[
                "medium_risk_duration"
            ],
            30,
        )

        # Three notifications occurred.
        self.assertEqual(
            saved[
                "total_alert_count"
            ],
            3,
        )

        self.assertEqual(
            saved[
                "medium_risk_alert_count"
            ],
            3,
        )

        # REPEAT occurred twice.
        self.assertEqual(
            saved[
                "most_frequent_alert_event"
            ],
            "REPEAT",
        )

    # ========================================================
    # NO RISK EVENTS
    # ========================================================

    def test_summary_without_risk_events(
        self,
    ):
        result = self.client.post(
            "/sessions/1/summary",
            json=self.payload,
        )

        self.assertEqual(
            result.status_code,
            201,
            result.text,
        )

        saved = result.json()

        self.assertEqual(
            saved[
                "low_risk_duration"
            ],
            0,
        )

        self.assertEqual(
            saved[
                "medium_risk_duration"
            ],
            0,
        )

        self.assertEqual(
            saved[
                "high_risk_duration"
            ],
            0,
        )

        self.assertEqual(
            saved[
                "low_risk_alert_count"
            ],
            0,
        )

        self.assertEqual(
            saved[
                "medium_risk_alert_count"
            ],
            0,
        )

        self.assertEqual(
            saved[
                "high_risk_alert_count"
            ],
            0,
        )

        self.assertEqual(
            saved[
                "total_alert_count"
            ],
            0,
        )

        self.assertIsNone(
            saved[
                "most_frequent_alert_event"
            ]
        )

    # ========================================================
    # NO REPORT / UNFINISHED SESSION
    # ========================================================

    def test_no_report_and_unfinished_session(
        self,
    ):
        self.assertEqual(
            self.client.get(
                "/sessions/1/summary"
            ).status_code,
            404,
        )

        session = self.db.get(
            PostureSession,
            1,
        )

        for session_status in (
            "RUNNING",
            "PAUSED",
        ):
            session.status = (
                session_status
            )

            self.db.commit()

            response = self.client.post(
                "/sessions/1/summary",
                json=self.payload,
            )

            self.assertEqual(
                response.status_code,
                409,
            )

    # ========================================================
    # OWNERSHIP
    # ========================================================

    def test_other_user_cannot_read_or_write(
        self,
    ):
        result = self.client.post(
            "/sessions/1/summary",
            json=self.payload,
        )

        self.assertEqual(
            result.status_code,
            201,
            result.text,
        )

        self.app.dependency_overrides[
            get_current_user
        ] = lambda: SimpleNamespace(
            id=2
        )

        self.assertEqual(
            self.client.get(
                "/sessions/1/summary"
            ).status_code,
            404,
        )

        self.assertEqual(
            self.client.post(
                "/sessions/1/summary",
                json=self.payload,
            ).status_code,
            404,
        )

        response = self.client.get(
            "/summaries"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            response.json(),
            [],
        )

    # ========================================================
    # INPUT VALIDATION
    # ========================================================

    def test_invalid_measurements(
        self,
    ):
        invalid_changes = (
            {
                "detection_count": -1,
            },
            {
                "pose_detected_count": 21,
            },
            {
                "face_detected_count": True,
            },
            {
                "detection_count": 2.5,
            },
        )

        for change in invalid_changes:
            with self.subTest(
                change=change
            ):
                response = self.client.post(
                    "/sessions/1/summary",
                    json={
                        **self.payload,
                        **change,
                    },
                )

                self.assertEqual(
                    response.status_code,
                    422,
                    response.text,
                )

        for value in (
            float("nan"),
            float("inf"),
        ):
            with self.subTest(
                value=value
            ):
                with self.assertRaises(
                    ValueError
                ):
                    SessionSummaryCreate(
                        **{
                            **self.payload,
                            "average_neck": value,
                        }
                    )


if __name__ == "__main__":
    unittest.main()