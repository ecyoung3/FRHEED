"""
Main GUI for FRHEED.
"""
import logging
import sys

from PyQt6.QtWidgets import QApplication, QMainWindow

from frheed import utils
from frheed.widgets.rheed_widgets import RHEEDWidget

# Store reference to main window so it doesn't get garbage collected
windows = []


class FRHEED(QMainWindow):
    def __init__(self):
        # Get application BEFORE initializing
        self.app = QApplication.instance() or QApplication(sys.argv)

        # Initialize window
        super().__init__(parent=None)

        # Store reference so the window doesn't get garbage-collected
        windows.append(self)

        # Create the main widget
        self.rheed_widget = RHEEDWidget()
        self.setCentralWidget(self.rheed_widget)

        # Quit FRHEED when the last window closes
        self.app.lastWindowClosed.connect(self.app.quit)

        # Set window properties
        self.setWindowTitle("FRHEED")
        self.setWindowIcon(utils.get_icon("FRHEED"))

        # Show the window and center in the screen
        self.show()
        utils.fit_screen(self)

        # Start blocking event loop that ends when app is closed
        sys.exit(self.app.exec_())


def show() -> FRHEED:
    logging.info("Opening FRHEED...")
    return FRHEED()


if __name__ == "__main__":
    gui = show()
