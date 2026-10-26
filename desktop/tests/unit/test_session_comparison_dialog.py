import os
import unittest
from unittest.mock import patch


os.environ.setdefault(
    "QT_QPA_PLATFORM",
    "offscreen",
)


from PySide6.QtWidgets import QApplication

from app.ui.dialogs.session_comparison_dialog import (
    SessionComparisonDialog,
)
from app.ui.pages.history_page import (
    HistoryPage,
)


METHOD = (
    "POSTGUARD_MODIFIED_RULA_FRONT_VIEW_V1"
)


class SessionComparisonDialogTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(
        cls,
    ):
        cls.app = (
            QApplication.instance()
            or
            QApplication([])
        )

    def setUp(
        self,
    ):
        self.sessions = [
            {
                "session_id": 40,
                "status": "COMPLETED",
                "total_duration": 100,
                "paused_duration": 0,
            },
            {
                "session_id": 39,
                "status": "COMPLETED",
                "total_duration": 90,
                "paused_duration": 0,
            },
        ]

        self.summaries = [
            {
                "session_id": 40,
                "average_risk_score": 20.0,
                "minimum_risk_score": 0.0,
                "maximum_risk_score": 50.0,
                "total_alert_count": 1,
                "risk_score_method": METHOD,
            },
            {
                "session_id": 39,
                "average_risk_score": 30.0,
                "minimum_risk_score": 0.0,
                "maximum_risk_score": 83.0,
                "total_alert_count": 3,
                "risk_score_method": METHOD,
            },
        ]

    def test_default_comparison_previous_to_latest(
        self,
    ):
        dialog = SessionComparisonDialog(
            sessions=self.sessions,
            summaries=self.summaries,
        )

        self.addCleanup(
            dialog.deleteLater
        )

        self.assertEqual(
            dialog.session_a_combo.currentData(),
            39,
        )

        self.assertEqual(
            dialog.session_b_combo.currentData(),
            40,
        )

        self.assertEqual(
            dialog.progress_label.text(),
            (
                "ผลเมื่อเทียบกับครั้งก่อน: ดีขึ้น"
            ),
        )

        self.assertIn(
            "30.00",
            dialog.score_change_label.text(),
        )

        self.assertIn(
            "20.00",
            dialog.score_change_label.text(),
        )

        self.assertIn(
            "ลดลง 10.00",
            dialog.score_change_label.text(),
        )

        self.assertEqual(
            dialog.table.item(
                0,
                1,
            ).text(),
            "30.00",
        )

        self.assertEqual(
            dialog.table.item(
                0,
                2,
            ).text(),
            "20.00",
        )

        self.assertEqual(
            dialog.table.item(
                0,
                3,
            ).text(),
            "↓ 10.00",
        )

    def test_alert_rate_is_shown(
        self,
    ):
        dialog = SessionComparisonDialog(
            sessions=self.sessions,
            summaries=self.summaries,
        )

        self.addCleanup(
            dialog.deleteLater
        )

        # Previous:
        # 3 / 90 sec = 2.00 per min
        self.assertEqual(
            dialog.table.item(
                4,
                1,
            ).text(),
            "2.00",
        )

        # Latest:
        # 1 / 100 sec = 0.60 per min
        self.assertEqual(
            dialog.table.item(
                4,
                2,
            ).text(),
            "0.60",
        )

        self.assertIn(
            "↓",
            dialog.table.item(
                4,
                3,
            ).text(),
        )

    def test_method_is_not_visible_to_user(
        self,
    ):
        dialog = SessionComparisonDialog(
            sessions=self.sessions,
            summaries=self.summaries,
        )

        self.addCleanup(
            dialog.deleteLater
        )

        self.assertTrue(
            dialog.method_label.isHidden()
        )

    def test_compare_button_disabled_with_one_session(
        self,
    ):
        dialog = SessionComparisonDialog(
            sessions=[
                self.sessions[
                    0
                ]
            ],
            summaries=[
                self.summaries[
                    0
                ]
            ],
        )

        self.addCleanup(
            dialog.deleteLater
        )

        self.assertFalse(
            dialog.compare_button.isEnabled()
        )

        self.assertIn(
            "อย่างน้อย 2 Session",
            dialog.explanation_label.text(),
        )

    def test_same_session_explains_problem(
        self,
    ):
        dialog = SessionComparisonDialog(
            sessions=self.sessions,
            summaries=self.summaries,
        )

        self.addCleanup(
            dialog.deleteLater
        )

        dialog.session_a_combo.setCurrentIndex(
            0
        )

        dialog.session_b_combo.setCurrentIndex(
            0
        )

        dialog.refresh_comparison()

        self.assertIn(
            "เลือกคนละครั้ง",
            dialog.progress_label.text(),
        )

    def test_history_opens_comparison_dialog(
        self,
    ):
        page = HistoryPage()

        self.addCleanup(
            page.deleteLater
        )

        page.sessions = list(
            self.sessions
        )

        page.summaries = list(
            self.summaries
        )

        page._update_compare_button()

        self.assertTrue(
            page.compare_button.isEnabled()
        )

        with patch(
            (
                "app.ui.pages.history_page."
                "SessionComparisonDialog"
            )
        ) as dialog_class:
            page.open_session_comparison()

            dialog_class.assert_called_once_with(
                sessions=page.sessions,
                summaries=page.summaries,
                parent=page,
            )

            dialog_class.return_value.exec.assert_called_once()


if __name__ == "__main__":
    unittest.main()