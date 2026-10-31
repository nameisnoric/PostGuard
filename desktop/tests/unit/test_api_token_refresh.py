import unittest
from unittest.mock import Mock, patch

from app.core.token_store import TokenStore
from app.services.api_client import APIClient


def response(status_code, data=None):
    result = Mock()
    result.status_code = status_code
    result.json.return_value = data or {}
    return result


class APITokenRefreshTests(unittest.TestCase):
    def tearDown(self):
        TokenStore.clear_token()

    def test_401_refreshes_and_retries_authenticated_request_once(self):
        TokenStore.set_session("expired-access", "valid-refresh", 1800)
        unauthorized = response(401, {"detail": "Invalid or Expired token"})
        success = response(200, {"status": "PAUSED"})
        refreshed = response(200, {
            "access_token": "new-access",
            "refresh_token": "new-refresh",
            "expires_in": 1800,
        })

        with patch("app.services.api_client.requests.patch", side_effect=[unauthorized, success]) as request, patch(
            "app.services.api_client.requests.post", return_value=refreshed
        ) as refresh:
            result = APIClient.patch("/sessions/44/pause")

        self.assertIs(result, success)
        self.assertEqual(request.call_count, 2)
        self.assertEqual(
            request.call_args_list[1].kwargs["headers"]["Authorization"],
            "Bearer new-access",
        )
        refresh.assert_called_once()
        self.assertEqual(TokenStore.get_refresh_token(), "new-refresh")

    def test_public_login_401_does_not_refresh_or_retry(self):
        TokenStore.set_session("old-access", "refresh", 1800)
        unauthorized = response(401)
        with patch("app.services.api_client.requests.post", return_value=unauthorized) as request:
            result = APIClient.login("user@ku.th", "wrong-password")
        self.assertIs(result, unauthorized)
        request.assert_called_once()

    def test_invalid_refresh_clears_credentials(self):
        TokenStore.set_session("expired-access", "expired-refresh", 1800)
        with patch("app.services.api_client.requests.get", return_value=response(401)) as request, patch(
            "app.services.api_client.requests.post", return_value=response(401)
        ):
            result = APIClient.get("/sessions")
        self.assertEqual(result.status_code, 401)
        request.assert_called_once()
        self.assertIsNone(TokenStore.get_token())
        self.assertIsNone(TokenStore.get_refresh_token())


if __name__ == "__main__":
    unittest.main()
