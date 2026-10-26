"""Reusable dialog for displaying a persisted PostGuard Session Report."""

from PySide6.QtWidgets import (
    QDialog,
    QScrollArea,
    QVBoxLayout,
)

from app.ui.pages.session_summary_page import (
    SessionSummaryPage,
)
from app.ui.theme import APP_QSS


class SavedSessionReportDialog(
    QDialog
):
    """
    Display an already-persisted PostGuard Session Summary.

    This dialog does not:
    - recalculate Detection
    - recalculate Risk Evaluation
    - recalculate Modified RULA
    - create a new Session Summary

    It only displays data already stored by Backend.
    """

    def __init__(
        self,
        *,
        session: dict,
        saved_summary: dict,
        parent=None,
    ):
        super().__init__(
            parent
        )

        if not isinstance(
            session,
            dict,
        ):
            raise ValueError(
                "Invalid session"
            )

        if not isinstance(
            saved_summary,
            dict,
        ):
            raise ValueError(
                "Invalid saved_summary"
            )

        session_id = session.get(
            "session_id"
        )

        saved_session_id = (
            saved_summary.get(
                "session_id"
            )
        )

        if (
            type(session_id) is not int
            or
            session_id <= 0
        ):
            raise ValueError(
                "Invalid session_id"
            )

        if (
            saved_session_id
            !=
            session_id
        ):
            raise ValueError(
                "Saved Summary session_id mismatch"
            )

        # ====================================================
        # WINDOW
        # ====================================================

        self.setWindowTitle(
            (
                "PostGuard - Saved Session Report "
                f"#{session_id}"
            )
        )

        self.resize(
            1100,
            820,
        )

        self.setMinimumSize(
            820,
            620,
        )

        self.setStyleSheet(
            APP_QSS
        )

        dialog_layout = QVBoxLayout(
            self
        )

        dialog_layout.setContentsMargins(
            12,
            12,
            12,
            12,
        )

        # ====================================================
        # SCROLL AREA
        # ====================================================

        scroll = QScrollArea(
            self
        )

        scroll.setWidgetResizable(
            True
        )

        # ====================================================
        # REPORT PAGE
        # ====================================================

        self.report_page = (
            SessionSummaryPage()
        )

        self.report_page.set_saved_report(
            session,
            saved_summary,
        )

        self.report_page.back_requested.connect(
            self.accept
        )

        scroll.setWidget(
            self.report_page
        )

        dialog_layout.addWidget(
            scroll
        )