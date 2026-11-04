import os
import unittest

os.environ.setdefault(
    "QT_QPA_PLATFORM",
    "offscreen",
)

from PySide6.QtCore import QPoint
from PySide6.QtGui import QPixmap
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication

from app.ui.widgets.monitoring_mini_controller import (
    MonitoringMiniController,
)


class MonitoringMiniControllerTests(
    unittest.TestCase
):
    @classmethod
    def setUpClass(
        cls,
    ):
        cls.app = (
            QApplication.instance()
            or QApplication([])
        )

    def setUp(
        self,
    ):
        self.widget = (
            MonitoringMiniController()
        )

        self.addCleanup(
            self._cleanup_widget
        )

    def _cleanup_widget(
        self,
    ):
        self.widget.hide_controller()
        self.widget.deleteLater()
        self.app.processEvents()

    def test_format_elapsed_time(
        self,
    ):
        self.assertEqual(
            self.widget._format_elapsed_time(0),
            "00:00:00",
        )

        self.assertEqual(
            self.widget._format_elapsed_time(3661),
            "01:01:01",
        )

    def test_refresh_state_reads_display_only_providers(
        self,
    ):
        pixmap = QPixmap(
            100,
            100,
        )

        self.widget.set_state_providers(
            elapsed_seconds_provider=lambda: 65,
            is_paused_provider=lambda: True,
            preview_pixmap_provider=lambda: pixmap,
            status_text_provider=lambda: "Paused",
        )

        self.widget.refresh_state()

        self.assertEqual(
            self.widget.elapsed_label.text(),
            "00:01:05",
        )

        self.assertEqual(
            self.widget.pause_button.text(),
            "Resume",
        )

        self.assertEqual(
            self.widget.status_label.text(),
            "Paused",
        )

        self.assertFalse(
            self.widget.preview_label
            .pixmap()
            .isNull()
        )

    def test_show_controller_starts_ui_refresh_timer(
        self,
    ):
        self.widget.show_controller()

        self.assertTrue(
            self.widget.isVisible()
        )

        self.assertTrue(
            self.widget.refresh_timer.isActive()
        )

    def test_hide_controller_stops_ui_refresh_timer(
        self,
    ):
        self.widget.show_controller()
        self.widget.hide_controller()

        self.assertFalse(
            self.widget.isVisible()
        )

        self.assertFalse(
            self.widget.refresh_timer.isActive()
        )

    def test_pause_button_emits_signal(
        self,
    ):
        spy = QSignalSpy(
            self.widget.pause_resume_requested
        )

        self.widget.pause_button.click()

        self.assertEqual(
            spy.count(),
            1,
        )

    def test_restore_button_emits_signal(
        self,
    ):
        spy = QSignalSpy(
            self.widget.restore_requested
        )

        self.widget.restore_button.click()

        self.assertEqual(
            spy.count(),
            1,
        )

    def test_end_button_emits_signal(
        self,
    ):
        spy = QSignalSpy(
            self.widget.end_requested
        )

        self.widget.end_button.click()

        self.assertEqual(
            spy.count(),
            1,
        )

    def test_clamp_keeps_widget_inside_available_geometry(
        self,
    ):
        self.widget.show_controller()

        geometry = (
            self.widget._available_geometry()
        )

        self.widget._move_clamped(
            QPoint(
                geometry.right() + 5000,
                geometry.bottom() + 5000,
            )
        )

        self.assertGreaterEqual(
            self.widget.x(),
            geometry.left(),
        )

        self.assertGreaterEqual(
            self.widget.y(),
            geometry.top(),
        )

        self.assertLessEqual(
            self.widget.frameGeometry().right(),
            geometry.right(),
        )

        self.assertLessEqual(
            self.widget.frameGeometry().bottom(),
            geometry.bottom(),
        )

    def test_snap_moves_near_left_edge_to_margin(
        self,
    ):
        self.widget.show_controller()

        geometry = (
            self.widget._available_geometry()
        )

        target_y = max(
            geometry.top() + self.widget.SCREEN_MARGIN,
            self.widget.y(),
        )

        self.widget.move(
            geometry.left()
            + self.widget.SCREEN_MARGIN
            + 5,
            target_y,
        )

        self.widget._snap_to_nearby_edge()

        self.assertEqual(
            self.widget.x(),
            geometry.left()
            + self.widget.SCREEN_MARGIN,
        )

    def test_hide_to_edge_does_not_destroy_widget(
        self,
    ):
        self.widget.show_controller()
        self.widget.hide_to_edge()

        self.assertTrue(
            self.widget._edge_hidden
        )

        self.assertTrue(
            self.widget.edge_tab_button.isVisible()
        )

        self.assertFalse(
            self.widget.content_container.isVisible()
        )

        self.assertTrue(
            self.widget.isVisible()
        )

    def test_reveal_from_edge_restores_full_controller(
        self,
    ):
        self.widget.show_controller()
        self.widget.hide_to_edge()
        self.widget.reveal_from_edge()

        self.assertFalse(
            self.widget._edge_hidden
        )

        self.assertFalse(
            self.widget.edge_tab_button.isVisible()
        )

        self.assertTrue(
            self.widget.header.isVisible()
        )

        self.assertTrue(
            self.widget.content_container.isVisible()
        )

        self.assertEqual(
            self.widget.width(),
            self.widget.DEFAULT_WIDTH,
        )

        self.assertEqual(
            self.widget.height(),
            self.widget.DEFAULT_HEIGHT,
        )

    def test_edge_hide_does_not_emit_end_signal(
        self,
    ):
        spy = QSignalSpy(
            self.widget.end_requested
        )

        self.widget.show_controller()
        self.widget.hide_to_edge()

        self.assertEqual(
            spy.count(),
            0,
        )

    def test_edge_reveal_does_not_emit_restore_signal(
        self,
    ):
        spy = QSignalSpy(
            self.widget.restore_requested
        )

        self.widget.show_controller()
        self.widget.hide_to_edge()
        self.widget.reveal_from_edge()

        self.assertEqual(
            spy.count(),
            0,
        )

    def test_close_event_emits_hide_not_end(
        self,
    ):
        hide_spy = QSignalSpy(
            self.widget.hide_requested
        )

        end_spy = QSignalSpy(
            self.widget.end_requested
        )

        self.widget.show_controller()
        self.widget.close()
        self.app.processEvents()

        self.assertEqual(
            hide_spy.count(),
            1,
        )

        self.assertEqual(
            end_spy.count(),
            0,
        )


if __name__ == "__main__":
    unittest.main()
