# -*- coding: utf-8 -*-
"""
Widgets for selecting things, including the source camera to use.
"""

from typing import Optional

from PyQt5.QtWidgets import (
    QWidget,
    QPushButton,
    QGridLayout,
    
    )
from PyQt5.QtCore import (
    Qt,
    pyqtSignal,
    
    )

from FRHEED.cameras.FLIR import FlirCamera
from FRHEED.cameras.USB import UsbCamera
from FRHEED.cameras import CameraError


class CameraSelection(QWidget):
    camera_classes = (
        FlirCamera,
        UsbCamera
        )
    camera_selected = pyqtSignal()
    
    def __init__(self):
        super().__init__(None)
        
        # Attributes to be assigned later
        self._cam: Optional[FlirCamera, UsbCamera] = None
        
        # Check for available cameras
        available = self.available_cameras()
        
        # Set window properties
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Window)
        self.setWindowTitle("Select Camera")
        
        # Set size
        self.setMinimumWidth(300)
        
        # Create layout
        self.layout = QGridLayout()
        self.setLayout(self.layout)
        
        # Create buttons for each camera
        for i, cam_class in enumerate(self.camera_classes):
            # Create the button
            btn = QPushButton(text=cam_class.__name__)
            btn.cam_class = cam_class
            
            # Disable button if camera is not available
            btn.setEnabled(cam_class in available)
            
            # Connect signal
            btn.clicked.connect(lambda: self.select_camera(btn.cam_class))
        
            # Add button to layout
            self.layout.addWidget(btn, i, 0)
            
        # Show the widget
        self.setVisible(True)
        
    def available_cameras(self) -> list:
        # Check each camera class for availability
        available = []
        for cam_class in self.camera_classes:
            print(f"Checking for {cam_class.__name__}...")
            try:
                with cam_class() as cam:
                    if cam.initialized:
                        available.append(cam_class)
                        print(f"{cam_class.__name__} is available")
                    else:
                        print(f"{cam_class.__name__} not available")
            except CameraError:
                print(f"No {cam_class.__name__} detected")
            finally:
                print("")
                
        return available
    
    def select_camera(self, cam_class) -> object:
        """ Get the selected camera class object. """
        # Deselect existing camera
        try:
            self._cam.close()
        except:
            pass
        
        # Initialize camera
        self._cam = cam_class()
        print(f"Connected to {cam_class.__name__}")
        
        # Emit camera_selected signal
        self.camera_selected.emit()
        
        # Hide the selection widget
        self.setVisible(False)
        
        return self._cam


if __name__ == "__main__":
    cam_select = CameraSelection()
