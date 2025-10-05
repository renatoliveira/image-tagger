"""Main application entry point for Image Tagger"""

import sys
from PyQt6.QtWidgets import QApplication
from ui.main_window import ImageTaggerMainWindow


def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    app.setApplicationName("Image Tagger")
    app.setApplicationVersion("1.0")

    window = ImageTaggerMainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()