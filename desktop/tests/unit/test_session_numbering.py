import unittest

from app.ui.utils.session_numbering import (
    build_session_number_map,
    session_number_text,
)


class SessionNumberingTests(unittest.TestCase):
    def test_non_consecutive_database_ids_become_user_sequence(self):
        sessions = [
            {"session_id": 89, "started_at": "2026-11-02T11:19:04Z"},
            {"session_id": 76, "started_at": "2026-11-01T23:54:04Z"},
            {"session_id": 87, "started_at": "2026-11-02T08:47:18Z"},
        ]
        numbers = build_session_number_map(sessions)
        self.assertEqual(numbers, {76: 1, 87: 2, 89: 3})
        self.assertEqual(session_number_text(89, numbers), "3")

    def test_missing_dates_fall_back_to_database_order(self):
        numbers = build_session_number_map([
            {"session_id": 10},
            {"session_id": 4},
        ])
        self.assertEqual(numbers, {4: 1, 10: 2})


if __name__ == "__main__":
    unittest.main()
