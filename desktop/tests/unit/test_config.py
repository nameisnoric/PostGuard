import unittest

from app.core.config import normalize_api_base_url


class DesktopConfigTests(unittest.TestCase):
    def test_default_and_trailing_slash_are_normalized(self):
        self.assertEqual(
            normalize_api_base_url(None),
            "http://127.0.0.1:8001",
        )
        self.assertEqual(
            normalize_api_base_url(" https://api.postguardapp.xyz/ "),
            "https://api.postguardapp.xyz",
        )

    def test_invalid_scheme_is_rejected(self):
        with self.assertRaises(ValueError):
            normalize_api_base_url("api.postguardapp.xyz")


if __name__ == "__main__":
    unittest.main()
