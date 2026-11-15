import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.ui.components.monitoring.monitoring_risk_card import MetricValueLabel


class MonitoringRiskCardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_risk_level_is_presented_in_thai_without_internal_label(self):
        label = MetricValueLabel(("ระดับความเสี่ยง:",))
        label.setText("ระดับความเสี่ยง: LOW (ต้นแบบ PostGuard)")
        self.assertEqual(label.text(), "ต่ำ")

    def test_complete_assessment_is_presented_as_evaluated(self):
        label = MetricValueLabel(("ผลการประเมิน:",))
        label.setText("ผลการประเมิน: COMPLETE")
        self.assertEqual(label.text(), "ประเมินแล้ว")

    def test_not_evaluated_state_never_exposes_internal_code(self):
        risk_label = MetricValueLabel(("ระดับความเสี่ยง:",))
        assessment_label = MetricValueLabel(("ผลการประเมิน:",))

        risk_label.setText("ระดับความเสี่ยง: N/A (NOT_EVALUATED)")
        assessment_label.setText("ผลการประเมิน: NOT_EVALUATED")

        self.assertEqual(risk_label.text(), "กำลังประเมิน")
        self.assertEqual(assessment_label.text(), "กำลังประเมิน")
        self.assertNotIn("N/A", risk_label.text())
        self.assertNotIn("NOT_EVALUATED", risk_label.text())

    def test_alert_decision_is_presented_as_a_status(self):
        label = MetricValueLabel(
            ("สถานะการแจ้งเตือน:", "การแจ้งเตือน:")
        )

        label.setText("สถานะการแจ้งเตือน: NO_ALERT")
        self.assertEqual(label.text(), "ไม่มีการแจ้งเตือน")

        label.setText("สถานะการแจ้งเตือน: ALERT | FIRST | HIGH")
        self.assertEqual(label.text(), "แจ้งเตือนแล้ว")


if __name__ == "__main__":
    unittest.main()
