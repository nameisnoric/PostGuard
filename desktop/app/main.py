import sys

from PySide6.QtWidgets import QApplication, QWidget

from app.ui.login_window import LoginWindow

def main() -> None:
    app = QApplication(sys.argv)

    window = LoginWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()