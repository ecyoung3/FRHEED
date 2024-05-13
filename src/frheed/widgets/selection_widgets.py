"""
Widgets for selecting things, including the source camera to use.
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QGridLayout, QPushButton, QWidget

from frheed.cameras.flir import FlirCamera
from frheed.cameras.flir import get_available_cameras as get_flir_cams
from frheed.cameras.usb import UsbCamera
from frheed.cameras.usb import get_available_cameras as get_usb_cams
from frheed.utils import get_icon


class CameraClasses(Enum):
    flir = FlirCamera
    usb = UsbCamera


@dataclass
class CameraObject:
    cam_class: type[FlirCamera] | type[UsbCamera]
    src: str | int
    name: str | None = None

    def get_camera(self) -> FlirCamera | UsbCamera:
        return self.cam_class(src=self.src)


class CameraSelection(QWidget):
    camera_classes = (FlirCamera, UsbCamera)
    camera_selected = pyqtSignal()

    def __init__(self) -> None:
        super().__init__(None)

        # NOTE: No parent is provided so the window can be minimized to the taskbar
        # TODO: Apply global stylesheet

        # Reference to Camera object that will be instantiated later
        self._cam: FlirCamera | UsbCamera | None = None

        # Check for available cameras
        cams = self.available_cameras()

        # Set window properties
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Window)
        self.setWindowTitle("Select Camera")
        self.setWindowIcon(get_icon("FRHEED"))

        # Set size
        self.setMinimumWidth(300)

        # Create layout
        layout = QGridLayout()
        self.setLayout(layout)

        # If there are no cameras, no buttons need to be added
        if not cams:
            btn = QPushButton("No cameras found")
            btn.setEnabled(False)
            layout.addWidget(btn, 0, 0)

        # Create buttons for each camera
        for i, cam in enumerate(cams):
            # Create the button
            btn = QPushButton(cam.name)

            # Connect signal
            # Doing it this way is necessary because otherwise all lambda
            # functions will initialize the same camera
            def make_lambda(cam_obj: CameraObject) -> Callable[[], FlirCamera | UsbCamera]:
                return lambda: self.select_camera(cam_obj)

            btn.clicked.connect(make_lambda(cam))

            # Add button to layout
            layout.addWidget(btn, i, 0)

        # Show the widget
        self.setVisible(True)

    def available_cameras(self) -> list[CameraObject]:
        # Check each camera class for availability
        usb_cams = [CameraObject(UsbCamera, src, name) for src, name in get_usb_cams().items()]
        flir_cams = [CameraObject(FlirCamera, src, name) for src, name in get_flir_cams().items()]
        return usb_cams + flir_cams

    def select_camera(self, cam: CameraObject) -> FlirCamera | UsbCamera:
        """Get the selected camera class object."""
        # Deselect existing camera
        if self._cam is not None:
            self._cam.close()

        # Initialize camera
        self._cam = cam.get_camera()

        # Emit camera_selected signal
        self.camera_selected.emit()

        # Hide the selection widget
        self.setVisible(False)

        return self._cam
