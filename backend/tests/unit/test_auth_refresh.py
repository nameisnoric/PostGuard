import unittest

try:
    from . import test_session_summaries as fixtures
except ImportError:
    import test_session_summaries as fixtures

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
)
from app.routers.auth import router as auth_router


class AuthRefreshTests(unittest.TestCase):
    def setUp(self):
        fixtures.SessionSummaryTests.setUp(self)
        self.app.include_router(auth_router)

    tearDown = fixtures.SessionSummaryTests.tearDown

    def test_refresh_returns_new_token_pair(self):
        result = self.client.post(
            "/auth/refresh",
            json={"refresh_token": create_refresh_token(1)},
        )
        self.assertEqual(result.status_code, 200, result.text)
        data = result.json()
        self.assertEqual(decode_access_token(data["access_token"]), 1)
        self.assertEqual(decode_refresh_token(data["refresh_token"]), 1)
        self.assertEqual(data["expires_in"], 1800)

    def test_access_token_cannot_be_used_as_refresh_token(self):
        result = self.client.post(
            "/auth/refresh",
            json={"refresh_token": create_access_token(1)},
        )
        self.assertEqual(result.status_code, 401)

    def test_refresh_token_cannot_be_used_as_access_token(self):
        with self.assertRaises(ValueError):
            decode_access_token(create_refresh_token(1))


if __name__ == "__main__":
    unittest.main()
