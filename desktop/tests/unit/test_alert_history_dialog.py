import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.services.api_client import APIClient
from app.ui.dialogs.alert_history_dialog import AlertHistoryDialog


def response(data, status=200):
    """
    สร้าง mock HTTP response ให้มี interface
    เหมือน response ที่ APIClient คืนกลับมา
    """
    return Mock(
        ok=status < 400,
        status_code=status,
        json=lambda: data,
        text="test",
    )


class AlertHistoryDialogTests(unittest.TestCase):
    """
    Unit tests สำหรับ AlertHistoryDialog ปัจจุบัน

    Architecture ที่ทดสอบ:

        Risk Event
            -> Alert Policy
            -> AlertNotification
            -> get_session_alert_notifications()
            -> AlertHistoryDialog

    ไม่ใช้ legacy get_session_alerts()
    """

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_dialog(self, notifications):
        """
        สร้าง Dialog โดย mock API ทั้งสองจุดที่ constructor ใช้งานจริง

        1. get_sessions()
           ใช้สร้าง Session Selector

        2. get_session_alert_notifications()
           ใช้โหลด AlertNotification ของ session ที่เลือก
        """
        sessions = [
            {
                "session_id": 11,
                "status": "COMPLETED",
                "started_at": "2026-10-15T04:41:46Z",
            },
            {
                "session_id": 12,
                "status": "COMPLETED",
                "started_at": "2026-10-15T04:48:28Z",
            },
        ]

        with patch.object(
            APIClient,
            "get_sessions",
            return_value=response(sessions),
        ), patch.object(
            APIClient,
            "get_session_alert_notifications",
            return_value=response(notifications),
        ):
            dialog = AlertHistoryDialog(session_id=12)

        self.addCleanup(dialog.deleteLater)

        return dialog

    def test_selected_session_and_empty_state_are_visible(self):
        """
        เมื่อ session ไม่มี AlertNotification:

        - session #12 ต้องถูกเลือก
        - empty state ต้องแสดง
        - table ต้องถูกซ่อน
        - จำนวน notification ทั้งหมดต้องเป็น 0
        """
        dialog = self.make_dialog([])

        self.assertEqual(
            dialog.session_selector.currentData(),
            12,
        )

        self.assertTrue(
            dialog.empty_label.isVisibleTo(dialog)
        )

        self.assertTrue(
            dialog.table.isHidden()
        )

        self.assertIn(
            "ทั้งหมด: 0",
            dialog.stats_label.text(),
        )

    def test_alert_rows_are_rendered(self):
        """
        ตรวจว่า AlertNotification ถูกนำมาแสดงในตาราง
        ตาม column mapping ของ implementation ปัจจุบัน
        """
        notifications = [
            {
                "notification_id": 21,
                "risk_event_id": 30,
                "session_id": 12,
                "alert_type": "FIRST",
                "risk_level": "MODERATE",
                "decision": "ALERT",
                "reason": "FIRST_ALERT_READY",
                "emitted_at": "2026-10-15T04:50:00Z",
                "created_at": "2026-10-15T04:50:00Z",
            }
        ]

        dialog = self.make_dialog(notifications)

        self.assertEqual(
            dialog.table.rowCount(),
            1,
        )

        self.assertFalse(
            dialog.table.isHidden()
        )

        # Column 0: Notification ID
        self.assertEqual(
            dialog.table.item(0, 0).text(),
            "21",
        )

        # Column 1: Risk Event ID
        self.assertEqual(
            dialog.table.item(0, 1).text(),
            "30",
        )

        # Column 2: Alert Type
        # implementation แปลงเป็น uppercase
        self.assertEqual(
            dialog.table.item(0, 2).text(),
            "FIRST",
        )

        # Column 3: Risk Level
        # implementation แปลงเป็น uppercase
        self.assertEqual(
            dialog.table.item(0, 3).text(),
            "MODERATE",
        )

        # Column 4: Decision
        self.assertEqual(
            dialog.table.item(0, 4).text(),
            "ALERT",
        )

        # Column 5: Reason
        self.assertEqual(
            dialog.table.item(0, 5).text(),
            "FIRST_ALERT_READY",
        )

    def test_notification_statistics_are_rendered(self):
        """
        ตรวจการนับ FIRST / REPEAT / ESCALATION
        ของ AlertNotification
        """
        notifications = [
            {
                "notification_id": 21,
                "risk_event_id": 30,
                "session_id": 12,
                "alert_type": "FIRST",
                "risk_level": "MODERATE",
                "decision": "ALERT",
                "reason": "FIRST_ALERT_READY",
                "emitted_at": "2026-10-15T04:50:00Z",
                "created_at": "2026-10-15T04:50:00Z",
            },
            {
                "notification_id": 22,
                "risk_event_id": 30,
                "session_id": 12,
                "alert_type": "REPEAT",
                "risk_level": "MODERATE",
                "decision": "ALERT",
                "reason": "REPEAT_ALERT_READY",
                "emitted_at": "2026-10-15T05:00:00Z",
                "created_at": "2026-10-15T05:00:00Z",
            },
            {
                "notification_id": 23,
                "risk_event_id": 30,
                "session_id": 12,
                "alert_type": "ESCALATION",
                "risk_level": "HIGH",
                "decision": "ALERT",
                "reason": "RISK_ESCALATED",
                "emitted_at": "2026-10-15T05:01:00Z",
                "created_at": "2026-10-15T05:01:00Z",
            },
        ]

        dialog = self.make_dialog(notifications)

        self.assertEqual(
            dialog.table.rowCount(),
            3,
        )

        stats = dialog.stats_label.text()

        self.assertIn(
            "ทั้งหมด: 3",
            stats,
        )

        self.assertIn(
            "ครั้งแรก: 1",
            stats,
        )

        self.assertIn(
            "ซ้ำ: 1",
            stats,
        )

        self.assertIn(
            "ระดับความเสี่ยงเพิ่มขึ้น: 1",
            stats,
        )


if __name__ == "__main__":
    unittest.main()