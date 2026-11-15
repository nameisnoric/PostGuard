import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.ui.theme import (
    FONT_FAMILY,
    FONT_PATH,
    install_application_font,
)


class ApplicationFontTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_bundled_noto_sans_thai_is_installed_globally(self):
        self.assertTrue(FONT_PATH.is_file())

        family = install_application_font(self.app)

        self.assertEqual(family, FONT_FAMILY)
        self.assertEqual(self.app.font().family(), FONT_FAMILY)
        self.assertIn('"Noto Sans Thai"', self.app.styleSheet())


if __name__ == "__main__":
    unittest.main()
