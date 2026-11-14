import unittest
from contextlib import contextmanager
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy.exc import OperationalError

from app.routers.health import health_check, readiness_check


class HealthRouterTests(unittest.TestCase):
    def test_liveness_does_not_require_external_dependencies(self):
        self.assertEqual(health_check()["status"], "ok")

    def test_readiness_confirms_database_connection(self):
        connection = unittest.mock.Mock()

        @contextmanager
        def connected():
            yield connection

        with patch("app.routers.health.engine.connect", connected):
            payload = readiness_check()

        connection.execute.assert_called_once()
        self.assertEqual(payload["status"], "ready")

    def test_readiness_hides_database_error_details(self):
        database_error = OperationalError(
            "SELECT 1",
            {},
            RuntimeError("secret database host"),
        )

        with patch(
            "app.routers.health.engine.connect",
            side_effect=database_error,
        ):
            with self.assertRaises(HTTPException) as raised:
                readiness_check()

        self.assertEqual(raised.exception.status_code, 503)
        self.assertNotIn(
            "secret database host",
            str(raised.exception.detail),
        )


if __name__ == "__main__":
    unittest.main()
