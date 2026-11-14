import importlib
import os
import unittest
from unittest.mock import patch

import app.core.config as config


class DesktopConfigTests(unittest.TestCase):
    def tearDown(self):
        importlib.reload(config)

    def test_default_api_url_supports_local_development(self):
        with patch.dict(os.environ, {}, clear=True):
            importlib.reload(config)

        self.assertEqual(config.API_BASE_URL, "http://127.0.0.1:8001")

    def test_api_url_can_be_configured_for_deployment(self):
        with patch.dict(
            os.environ,
            {"POSTGUARD_API_BASE_URL": "https://api.postguardapp.xyz/"},
            clear=True,
        ):
            importlib.reload(config)

        self.assertEqual(
            config.API_BASE_URL,
            "https://api.postguardapp.xyz",
        )


if __name__ == "__main__":
    unittest.main()
