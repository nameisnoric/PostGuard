import unittest

from app.ui.utils.camera_display import (
    camera_display_name,
    camera_display_number,
)


class CameraDisplayTests(unittest.TestCase):
    def test_explicit_display_number_is_one_based(self):
        camera = {
            "display_number": 1,
            "device_index": 7,
            "camera_id": 42,
            "camera_name": "Camera 7",
        }

        self.assertEqual(camera_display_number(camera), 1)
        self.assertEqual(camera_display_name(camera), "กล้องตัวที่ 1")

    def test_opencv_name_is_converted_to_user_number(self):
        self.assertEqual(
            camera_display_name({"camera_name": "Camera 0"}),
            "กล้องตัวที่ 1",
        )

    def test_real_camera_name_is_preserved_when_no_number_exists(self):
        self.assertEqual(
            camera_display_name({"camera_name": "Logitech Brio"}),
            "Logitech Brio",
        )


if __name__ == "__main__":
    unittest.main()
