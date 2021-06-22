# -*- coding: utf-8 -*-
"""
Widgets for selecting things, including the source camera to use.
"""

from typing import Optional, Union, List
from dataclasses import dataclass
from enum import Enum

from PyQt5.QtWidgets import (
    QWidget,
    QPushButton,
    QGridLayout,
    
    )
from PyQt5.QtCore import (
    Qt,
    pyqtSignal,
    
    )

from frheed.cameras.flir import FlirCamera, get_available_cameras as get_flir_cams
from frheed.cameras.usb import UsbCamera, get_available_cameras as get_usb_cams
from frheed.cameras import CameraError
from frheed.utils import get_icon


class CameraClasses(Enum):
    flir = FlirCamera
    usb = UsbCamera


@dataclass
class CameraObject:
    cam_class: object
    src: Union[str, int]
    name: Optional[str] = None
    
    def get_camera(self) -> Union[FlirCamera, UsbCamera]:
        return self.cam_class(src=self.src)


class CameraSelection(QWidget):
    camera_classes = (
        FlirCamera,
        UsbCamera
        )
    camera_selected = pyqtSignal()
    
    def __init__(self):
        super().__init__(None)
        
        # NOTE: No parent is provided so the window can be minimized to the taskbar
        # TODO: Apply global stylesheet
        
        # Attributes to be assigned later
        self._cam: Optional[FlirCamera, UsbCamera] = None
        
        # Check for available cameras
        cams = self.available_cameras()
        
        # Set window properties
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Window)
        self.setWindowTitle("Select Camera")
        self.setWindowIcon(get_icon("FRHEED"))
        
        # Set size
        self.setMinimumWidth(300)
        
        # Create layout
        self.layout = QGridLayout()
        self.setLayout(self.layout)
        
        # If there are no cameras, no buttons need to be added
        if not cams:
            btn = QPushButton("No cameras found")
            btn.setEnabled(False)
            self.layout.addWidget(btn, 0, 0)
        
        # Create buttons for each camera
        for i, cam in enumerate(cams):
            # Create the button
            btn = QPushButton(cam.name)
            
            # Connect signal
            # Doing it this way is necessary because otherwise all lambda
            # functions will initialize the same camera
            def make_lambda(cam_obj: CameraObject):
                return lambda: self.select_camera(cam_obj)
            btn.clicked.connect(make_lambda(cam))
        
            # Add button to layout
            self.layout.addWidget(btn, i, 0)
            
        # Show the widget
        self.setVisible(True)
        
    def available_cameras(self) -> List[CameraObject]:
        # Check each camera class for availability
        usb_cams = [CameraObject(UsbCamera, src, name) 
                    for src, name in get_usb_cams().items()]
        flir_cams = [CameraObject(FlirCamera, src, name)
                     for src, name in get_flir_cams().items()]
        return usb_cams + flir_cams
    
    def select_camera(self, cam: CameraObject) -> object:
        """ Get the selected camera class object. """
        # Deselect existing camera
        try:
            self._cam.close()
        except:
            pass
        
        # Initialize camera
        self._cam = cam.get_camera()
        print(f"Connected to {cam.name}")
        
        # Emit camera_selected signal
        self.camera_selected.emit()
        
        # Hide the selection widget
        self.setVisible(False)
        
        return self._cam
    

if __name__ == "__main__":
    cam_select = CameraSelection()
