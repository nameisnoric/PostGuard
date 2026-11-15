import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel

from app.ui.utils.preview_sizing import fit_preview_label, fitted_preview_size


class CountingLabel(QLabel):
    def __init__(self):
        self.geometry_updates = 0
        super().__init__()

    def updateGeometry(self):
        self.geometry_updates += 1
        super().updateGeometry()


class PreviewSizingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_four_by_three_frame_uses_available_height_without_side_panels(self):
        self.assertEqual(fitted_preview_size(640, 480, 960, 540), (720, 540))
        self.assertEqual(fitted_preview_size(640, 480, 720, 480), (640, 480))

    def test_sixteen_by_nine_frame_uses_full_preview_width(self):
        self.assertEqual(fitted_preview_size(1280, 720, 960, 540), (960, 540))
        self.assertEqual(fitted_preview_size(1280, 720, 720, 480), (720, 405))

    def test_invalid_frame_dimensions_are_rejected(self):
        with self.assertRaises(ValueError):
            fitted_preview_size(0, 720, 960, 540)

    def test_unchanged_preview_does_not_request_layout_again(self):
        label = CountingLabel()

        fit_preview_label(label, 1280, 720, 720, 480)
        updates_after_first_fit = label.geometry_updates

        fit_preview_label(label, 1280, 720, 720, 480)

        self.assertEqual(label.geometry_updates, updates_after_first_fit)


if __name__ == "__main__":
    unittest.main()
