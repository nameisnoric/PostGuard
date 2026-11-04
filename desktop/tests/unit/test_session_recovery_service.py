import unittest
from unittest.mock import Mock, patch

import requests

from app.services.api_client import APIClient
from app.services.session_recovery_service import (
    find_unclosed_sessions,
    interrupt_previous_session,
)


def response(
    data,
    status=200,
):
    return Mock(
        ok=status < 400,
        status_code=status,
        json=lambda: data,
        text="test",
    )


class SessionRecoveryServiceTests(
    unittest.TestCase
):

    # =========================================================
    # FIND UNCLOSED SESSION
    # =========================================================

    @patch.object(
        APIClient,
        "get_sessions",
    )
    def test_find_unclosed_sessions_returns_only_running_and_paused(
        self,
        get_sessions,
    ):
        get_sessions.return_value = response(
            [
                {
                    "session_id": 1,
                    "status": "RUNNING",
                },
                {
                    "session_id": 2,
                    "status": "PAUSED",
                },
                {
                    "session_id": 3,
                    "status": "COMPLETED",
                },
                {
                    "session_id": 4,
                    "status": "INTERRUPTED",
                },
                {
                    "session_id": 5,
                    "status": "ENDED",
                },
            ]
        )

        result = find_unclosed_sessions()

        self.assertEqual(
            [
                session["session_id"]
                for session in result
            ],
            [1, 2],
        )

    @patch.object(
        APIClient,
        "get_sessions",
    )
    def test_find_unclosed_sessions_returns_empty_when_none_active(
        self,
        get_sessions,
    ):
        get_sessions.return_value = response(
            [
                {
                    "session_id": 1,
                    "status": "COMPLETED",
                },
                {
                    "session_id": 2,
                    "status": "INTERRUPTED",
                },
            ]
        )

        result = find_unclosed_sessions()

        self.assertEqual(
            result,
            [],
        )

    @patch.object(
        APIClient,
        "get_sessions",
    )
    def test_find_unclosed_sessions_rejects_http_failure(
        self,
        get_sessions,
    ):
        get_sessions.return_value = response(
            {},
            503,
        )

        with self.assertRaises(
            RuntimeError
        ):
            find_unclosed_sessions()

    @patch.object(
        APIClient,
        "get_sessions",
    )
    def test_find_unclosed_sessions_rejects_non_list_response(
        self,
        get_sessions,
    ):
        get_sessions.return_value = response(
            {
                "session_id": 1,
                "status": "RUNNING",
            }
        )

        with self.assertRaises(
            ValueError
        ):
            find_unclosed_sessions()

    @patch.object(
        APIClient,
        "get_sessions",
    )
    def test_find_unclosed_sessions_rejects_unknown_status(
        self,
        get_sessions,
    ):
        get_sessions.return_value = response(
            [
                {
                    "session_id": 1,
                    "status": "UNKNOWN",
                }
            ]
        )

        with self.assertRaises(
            ValueError
        ):
            find_unclosed_sessions()

    @patch.object(
        APIClient,
        "get_sessions",
    )
    def test_find_unclosed_sessions_rejects_invalid_session_id(
        self,
        get_sessions,
    ):
        get_sessions.return_value = response(
            [
                {
                    "session_id": 0,
                    "status": "RUNNING",
                }
            ]
        )

        with self.assertRaises(
            ValueError
        ):
            find_unclosed_sessions()

    # =========================================================
    # INTERRUPT PREVIOUS SESSION
    # =========================================================

    @patch.object(
        APIClient,
        "interrupt_session",
    )
    def test_interrupt_previous_session_accepts_backend_confirmation(
        self,
        interrupt_session,
    ):
        interrupt_session.return_value = response(
            {
                "session_id": 7,
                "status": "INTERRUPTED",
            }
        )

        interrupt_previous_session(
            7
        )

        interrupt_session.assert_called_once_with(
            7
        )

    @patch.object(
        APIClient,
        "interrupt_session",
    )
    def test_interrupt_previous_session_rejects_http_failure(
        self,
        interrupt_session,
    ):
        interrupt_session.return_value = response(
            {},
            503,
        )

        with self.assertRaises(
            RuntimeError
        ):
            interrupt_previous_session(
                7
            )

    @patch.object(
        APIClient,
        "interrupt_session",
    )
    def test_interrupt_previous_session_requires_interrupted_status(
        self,
        interrupt_session,
    ):
        interrupt_session.return_value = response(
            {
                "session_id": 7,
                "status": "RUNNING",
            }
        )

        with self.assertRaises(
            ValueError
        ):
            interrupt_previous_session(
                7
            )

    @patch.object(
        APIClient,
        "interrupt_session",
    )
    def test_interrupt_previous_session_requires_same_session_id(
        self,
        interrupt_session,
    ):
        interrupt_session.return_value = response(
            {
                "session_id": 99,
                "status": "INTERRUPTED",
            }
        )

        with self.assertRaises(
            ValueError
        ):
            interrupt_previous_session(
                7
            )

    # =========================================================
    # NETWORK LOSS AFTER WRITE
    # =========================================================

    @patch.object(
        APIClient,
        "get_session",
    )
    @patch.object(
        APIClient,
        "interrupt_session",
    )
    def test_network_failure_rechecks_backend_state(
        self,
        interrupt_session,
        get_session,
    ):
        interrupt_session.side_effect = (
            requests.RequestException(
                "connection lost"
            )
        )

        get_session.return_value = response(
            {
                "session_id": 7,
                "status": "INTERRUPTED",
            }
        )

        interrupt_previous_session(
            7
        )

        interrupt_session.assert_called_once_with(
            7
        )

        get_session.assert_called_once_with(
            7
        )

    @patch.object(
        APIClient,
        "get_session",
    )
    @patch.object(
        APIClient,
        "interrupt_session",
    )
    def test_network_failure_does_not_assume_write_succeeded(
        self,
        interrupt_session,
        get_session,
    ):
        interrupt_session.side_effect = (
            requests.RequestException(
                "connection lost"
            )
        )

        get_session.return_value = response(
            {
                "session_id": 7,
                "status": "RUNNING",
            }
        )

        with self.assertRaises(
            ValueError
        ):
            interrupt_previous_session(
                7
            )

    @patch.object(
        APIClient,
        "get_session",
    )
    @patch.object(
        APIClient,
        "interrupt_session",
    )
    def test_network_failure_and_failed_recheck_raises(
        self,
        interrupt_session,
        get_session,
    ):
        interrupt_session.side_effect = (
            requests.RequestException(
                "connection lost"
            )
        )

        get_session.return_value = response(
            {},
            503,
        )

        with self.assertRaises(
            RuntimeError
        ):
            interrupt_previous_session(
                7
            )


if __name__ == "__main__":
    unittest.main()