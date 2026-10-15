import unittest

from app.ui.preview_sizing import fitted_preview_size


class PreviewSizingTests(unittest.TestCase):
    def test_four_by_three_frame_uses_available_height_without_side_panels(self):
        self.assertEqual(fitted_preview_size(640, 480, 960, 540), (720, 540))
        self.assertEqual(fitted_preview_size(640, 480, 720, 480), (640, 480))

    def test_sixteen_by_nine_frame_uses_full_preview_width(self):
        self.assertEqual(fitted_preview_size(1280, 720, 960, 540), (960, 540))
        self.assertEqual(fitted_preview_size(1280, 720, 720, 480), (720, 405))

    def test_invalid_frame_dimensions_are_rejected(self):
        with self.assertRaises(ValueError):
            fitted_preview_size(0, 720, 960, 540)


if __name__ == "__main__":
    unittest.main()
