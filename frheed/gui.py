# -*- coding: utf-8 -*-

import sys

from PyQt5.QtWidgets import QMainWindow, QApplication

from frheed.widgets.rheed_widgets import RHEEDWidget
from frheed.utils import get_logger


logger = get_logger()
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
        
        # Set window properties
        self.setWindowTitle("FRHEED")


def show() -> FRHEED:
    from frheed.utils import test_widget
    logger.info("Opening FRHEED...")
    gui, app = test_widget(FRHEED, block=True)
    return gui


if __name__ == "__main__":
    gui = show()