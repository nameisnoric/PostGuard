import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.ui.dialogs.rula_assessment_dialog import RulaAssessmentDialog


class RulaAssessmentDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_camera_suggestion_and_complete_result(self):
        dialog = RulaAssessmentDialog({
            "neck_score_lower_bound": 3,
            "muscle_use_score": 1,
        })
        self.assertEqual(dialog.controls["neck"].currentData(), 3)
        self.assertEqual(dialog.controls["muscle_use_b"].currentData(), 1)

        dialog._calculate()

        self.assertEqual(dialog.result_data["status"], "COMPLETE")
        self.assertIn(dialog.result_data["final_score"], range(1, 8))
        self.assertIn(dialog.result_data["action_level"], range(1, 5))
        dialog.deleteLater()


if __name__ == "__main__":
    unittest.main()
