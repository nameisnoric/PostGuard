import sys

from PySide6.QtWidgets import QApplication, QWidget

from app.ui.theme import install_application_font
from app.ui.windows.login_window import LoginWindow

def main() -> None:
    app = QApplication(sys.argv)
    install_application_font(app)

    window = LoginWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
