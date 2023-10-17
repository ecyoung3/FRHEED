"""
PyQt widgets for camera streaming and settings.
https://stackoverflow.com/a/33453124/10342097
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from typing import Any

import cv2
import numpy as np
from PyQt6.QtCore import (
    QCoreApplication,
    QEvent,
    QObject,
    QSize,
    Qt,
    QThread,
    pyqtBoundSignal,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtGui import QCloseEvent, QKeyEvent, QWheelEvent
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QStatusBar,
    QWidget,
)

import frheed.utils as utils
from frheed.cameras import CameraError
from frheed.cameras.flir import FlirCamera
from frheed.cameras.usb import UsbCamera
from frheed.constants import DATA_DIR
from frheed.image_processing import (
    apply_cmap,
    column_to_image,
    extend_image,
    get_valid_colormaps,
    ndarray_to_qpixmap,
    to_grayscale,
)
from frheed.widgets.canvas_widget import CanvasShape, CanvasWidget
from frheed.widgets.common_widgets import DoubleSlider, HLine, SliderLabel

MIN_ZOOM = 0.20
MAX_ZOOM = 2.0
MIN_W = 480
MIN_H = 348
MAX_W = 2560
MAX_H = 2560
DEFAULT_CMAP = "Spectral"
DEFAULT_INTERPOLATION = cv2.INTER_CUBIC


class VideoWidget(QWidget):
    """Holds the camera frame and toolbar buttons"""

    frame_changed = pyqtSignal()
    frame_ready = pyqtSignal(np.ndarray)
    _min_w = 480
    _min_h = 348
    _max_w = MAX_W

    def __init__(self, camera: FlirCamera | UsbCamera, parent=None, zoomable: bool = True):
        super().__init__(parent)

        # Store colormap
        self._colormap = DEFAULT_CMAP

        # Whether or not image can be zoomed in/out
        self._zoomable = zoomable

        # Video writer for saving video
        self._writer: cv2.VideoWriter | None = None

        # Store camera reference and start the camera
        self.set_camera(camera)

        # Frame settings
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)
        self.setMinimumSize(QSize(MIN_W, MIN_H))
        self.setMouseTracking(True)

        # Create main layout (2 rows x 1 column)
        self.main_layout = QGridLayout()
        self.setLayout(self.main_layout)
        self.main_layout.setContentsMargins(4, 4, 4, 4)
        self.main_layout.setSpacing(4)

        # Create toolbar layout
        self.toolbar_layout = QGridLayout()
        self.toolbar_layout.setContentsMargins(0, 0, 0, 0)
        self.toolbar_layout.setSpacing(4)

        # Create capture button for saving an image of the current frame
        self.capture_button = QPushButton("Capture", self)
        self.capture_button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)

        # Create record button for saving video
        self.record_button = QPushButton("Start Recording", self)
        self.record_button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)

        # Create start/stop button
        self.play_button = QPushButton("Stop Camera")
        self.play_button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)

        # Determine maximum zoom because huge images cause lag
        cam_w, cam_h = camera.width, camera.height
        max_zoom = max(min(MAX_ZOOM, (MAX_W / cam_w), (MAX_H / cam_h)), 1)

        # Create zoom slider
        self.slider = DoubleSlider(decimals=2, log=False, parent=self)
        self.slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.slider.setMinimum(MIN_ZOOM)
        self.slider.setMaximum(max_zoom)
        self.slider.setValue(1.0)
        self.slider.setSingleStep(0.01)
        self.slider.setTickPosition(QSlider.TickPosition.TicksAbove)
        self.slider.setTickInterval(0.10)
        self.slider.setOrientation(Qt.Orientation.Horizontal)

        # Create zoom label
        self.zoom_label = SliderLabel(self.slider, name="Zoom", precision=2)

        # Create button for opening settings
        self.settings_button = QPushButton()
        self.settings_button.setText("Edit Settings")
        self.settings_button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)

        # Create button for opening output folder
        self.folder_button = QPushButton()
        # TODO: Finish functionality of this button

        # Create settings widget
        self.make_camera_settings_widget()

        # Create display for showing camera frame
        self.display = CameraDisplay(self)

        # Create scroll area for holding camera frame
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setWidget(self.display)
        self.scroll_area.installEventFilter(self)

        # Create status bar
        self.status_bar = CameraStatusBar(self)

        # Add widgets
        self.main_layout.addLayout(self.toolbar_layout, 0, 0, 1, 1)
        self.toolbar_layout.addWidget(self.capture_button, 0, 0, 1, 1)
        self.toolbar_layout.addWidget(self.record_button, 0, 1, 1, 1)
        self.toolbar_layout.addWidget(self.play_button, 0, 2, 1, 1)
        self.toolbar_layout.addWidget(self.zoom_label, 0, 3, 1, 1)
        self.toolbar_layout.addWidget(self.slider, 0, 4, 1, 1)
        self.toolbar_layout.addWidget(self.settings_button, 0, 5, 1, 1)
        self.main_layout.addWidget(self.scroll_area, 1, 0, 1, 1)
        self.main_layout.addWidget(self.status_bar, 2, 0, 1, 1)

        # Connect signals
        self.capture_button.clicked.connect(self.save_image)
        self.record_button.clicked.connect(self.start_or_stop_recording)
        self.play_button.clicked.connect(self.start_or_stop_camera)
        self.settings_button.clicked.connect(self.edit_settings)
        self.slider.valueChanged.connect(self.display.force_resize)
        self.frame_changed.connect(self.status_bar.frame_changed)

        # Attributes to be assigned later
        self.frame: np.ndarray | None = None
        self.raw_frame: np.ndarray | None = None
        self.region_data: dict = {}
        self.analyze_frames = True

        # Set up the camera streaming thread
        self.camera_worker = CameraWorker(self)
        self.camera_thread = QThread()
        self.camera_worker.moveToThread(self.camera_thread)
        self.camera_worker.frame_ready.connect(self.show_frame)
        self.camera_worker.finished.connect(self.camera_thread.quit)
        self.camera_thread.started.connect(self.camera_worker.start)
        self.camera_thread.start()

        # Set up plotting thread
        self.analysis_worker = AnalysisWorker(self)
        self.analysis_thread = QThread()
        self.analysis_worker.moveToThread(self.analysis_thread)
        self.analysis_worker.finished.connect(self.analysis_thread.quit)
        self.analysis_thread.started.connect(self.analysis_worker.start)
        self.analysis_thread.start()

        # Connect other signals
        self.frame_ready.connect(self.analysis_worker.analyze_frame)

        # Variables to be used in properties
        self._workers: tuple[Worker, ...] = (self.camera_worker, self.analysis_worker)

    def __del__(self) -> None:
        """Close the camera when the widget is deleted."""
        self.camera.close()

    def eventFilter(self, obj: QObject | None, event: QEvent | None) -> bool:
        """Returns whether or not the event should be filtered out."""
        if obj == self.display.canvas:
            if type(event) == QKeyEvent:
                self.display.canvas.keyPressEvent(event)
        elif type(event) == QWheelEvent:
            if event.modifiers() == Qt.KeyboardModifier.ControlModifier and self.zoomable:
                # Zoom the camera if zooming is enabled
                # TODO: Keep frame location constant under mouse while zooming
                old_zoom = self.slider.value()
                step = self.slider.singleStep()
                dy = event.angleDelta().y()
                if dy < 0:
                    # Zoom out if scrolling down
                    self.slider.setValue(max(self.slider.minimum(), old_zoom - step))
                elif dy > 0:
                    # Zoom in if scrolling up
                    self.slider.setValue(min(self.slider.maximum(), old_zoom + step))
                return True
            elif obj == self.scroll_area:
                # Make sure scroll area doesn't scroll while CTRL is pressed
                self.scroll_area.wheelEvent(event)
                return True
        return False

    @pyqtSlot(QCloseEvent)
    def closeEvent(self, event: QCloseEvent | None) -> None:
        """Stop the camera and close settings when the widget is closed"""
        [worker.stop() for worker in self.workers]
        self.settings_widget.deleteLater()
        super().closeEvent(event)

    @pyqtSlot()
    def start_or_stop_camera(self) -> None:
        if self.camera.running:
            self.camera.stop()
            self.play_button.setText("Start Camera")
        else:
            self.camera.start(continuous=True)
            self.play_button.setText("Stop Camera")

    @pyqtSlot(np.ndarray)
    def show_frame(self, frame: np.ndarray) -> None:
        """Show the next camera frame"""
        # Store raw frame
        self.raw_frame = frame.copy()

        # Resize to display size and get dimensions
        frame = self._resize_frame(frame)

        # Convert to grayscale
        frame = to_grayscale(frame)

        # Emit the frame if analysis is needed
        self.frame_ready.emit(frame) if self.analyze_frames else None

        # Apply colormap
        frame = apply_cmap(frame, self.colormap)

        # Store the processed frame
        self.frame = frame.copy()

        # Write to video file if saving; expects frame to be same shape as writer with BGR channels
        if self._writer is not None:
            self._writer.write(cv2.cvtColor(self.frame, cv2.COLOR_RGB2BGR))

        # Create QPixmap from numpy array
        qpix = ndarray_to_qpixmap(frame)

        # Show the QPixmap
        self.display.label.setPixmap(qpix)

        # Emit frame_changed signal
        self.frame_changed.emit()

    @pyqtSlot()
    def save_image(self) -> str | None:
        """Save the currently displayed frame."""
        if self.frame is None:
            logging.warning("Cannot save image if the current frame is None")
            return None

        frame = self.frame.copy()
        tstamp = datetime.now().strftime("%d-%b-%Y_%H%M%S")
        filename = f"{tstamp}.png"
        filepath = os.path.join(DATA_DIR, filename)
        cv2.imwrite(filepath, frame)

        return filepath

    @pyqtSlot()
    def start_or_stop_recording(self) -> None:
        """Start or stop recording video."""
        if self.frame is None:
            logging.warning("Cannot start or stop recording if the current frame is None")
            return

        # If there is no video writer, create one and start recording
        # https://www.geeksforgeeks.org/saving-a-video-using-opencv/
        if self._writer is None:
            # Update button text
            self.record_button.setText("Stop Recording")

            # Generate filename
            tstamp = datetime.now().strftime("%d-%b-%Y_%H%M%S")
            filename = f"{tstamp}.avi"
            filepath = os.path.join(DATA_DIR, filename)

            # Disable resizing while video capture is active
            self.set_zoomable(False)

            # Disable play button
            self.play_button.setEnabled(False)

            # Create video writer
            fps = self.camera.real_fps
            h, w = self.frame.shape[:2]
            shape = (w, h)
            fourcc = cv2.VideoWriter.fourcc(*"MJPG")
            logging.info("Creating video writer with FPS = %.2f and shape = %s", fps, shape)
            self._writer = cv2.VideoWriter(filepath, fourcc=fourcc, fps=fps, frameSize=shape)

        # Otherwise, stop recording
        else:
            # Update button text
            self.record_button.setText("Start Recording")

            # Stop recording and release the writer
            self._writer.release()
            self._writer = None

            # Re-enable resizing
            self.set_zoomable(True)

            # Re-enable play button
            self.play_button.setEnabled(True)

    @pyqtSlot()
    def edit_settings(self) -> None:
        if hasattr(self.camera, "edit_settings"):
            self.camera.edit_settings()
        else:
            self.settings_widget.show()

    @pyqtSlot(str)
    def set_colormap(self, colormap: str) -> None:
        self.colormap = colormap

    @pyqtSlot()
    def resize_display(self) -> None:
        self.display.force_resize()

    @property
    def camera(self) -> FlirCamera | UsbCamera:
        return self._camera

    @camera.setter
    def camera(self, camera: FlirCamera | UsbCamera) -> None:
        if self._writer is not None:
            # Cannot set camera while recording
            QMessageBox.warning(self, "Warning", "Cannot change camera while recording video.")
            return

        # TODO: Fully implement this and test it
        self.set_camera(camera)

    @property
    def zoomable(self) -> bool:
        """Whether or not the frame can be zoomed in/out."""
        return self._zoomable

    @zoomable.setter
    def zoomable(self, zoomable: bool) -> None:
        self.set_zoomable(zoomable)

    @property
    def zoom(self) -> float:
        return self.slider.value()

    @property
    def workers(self) -> tuple:
        return self._workers

    @property
    def app(self) -> QCoreApplication | None:
        return QApplication.instance()

    @property
    def colormap(self) -> str:
        return self._colormap

    @colormap.setter
    def colormap(self, colormap: str) -> None:
        if colormap in get_valid_colormaps():
            self._colormap = colormap
            # TODO: Update label that shows current colormap

    def make_camera_settings_widget(self) -> None:
        self.settings_widget = CameraSettingsWidget(self)

    def set_camera(self, camera: FlirCamera | UsbCamera) -> None:
        """Set the camera to use as capture device for the display.

        Args:
            camera (Union[FlirCamera, UsbCamera]): The Camera object to use.

        Returns:
            None
        """
        if self._writer is not None:
            QMessageBox.warning(self, "Warning", "Cannot change camera while recording video.")
            return

        # Change the camera and start it
        self._camera = camera
        self._camera.start(continuous=True)

        # Update the zoom slider (if it has been created)
        if not hasattr(self, "slider"):
            return
        cam_w, cam_h = camera.width, camera.height
        max_zoom = max(min(MAX_ZOOM, (MAX_W / cam_w), (MAX_H / cam_h)), 1)
        self.slider.setMaximum(max_zoom)

        # Reset to 100% zoom
        self.slider.setValue(1.00)

        # Update camera settings widget
        self.make_camera_settings_widget()

    def start_analyzing_frames(self) -> None:
        self.analyze_frames = True

    def stop_analyzing_frames(self) -> None:
        self.analyze_frames = False

    def set_zoomable(self, zoomable: bool) -> None:
        """Toggle whether or not zooming in and out of the image is enabled."""
        # Return if setting hasn't changed
        if self.zoomable == zoomable:
            return

        # Update private setting
        self._zoomable = zoomable

        # Disable slider if not zoomable, otherwise enable
        self.slider.setEnabled(zoomable)

    def _start_workers(self) -> None:
        for worker in self._workers:
            worker.start()

    def _stop_workers(self) -> None:
        for worker in self._workers:
            worker.stop()

    def _resize_frame(self, frame: np.ndarray, interp: int = DEFAULT_INTERPOLATION) -> np.ndarray:
        size = self.display.sizeHint()
        w, h = size.width(), size.height()
        return cv2.resize(frame, dsize=(w, h), interpolation=interp)


class CameraDisplay(QWidget):
    """Displays the camera frame itself"""

    def __init__(self, parent: VideoWidget) -> None:
        super().__init__(parent)
        self._video_widget = parent

        # Settings
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)

        # Create layout
        self.main_layout = QGridLayout()
        self.setLayout(self.main_layout)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        # Create display label
        self.label = QLabel()
        self.label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # Create canvas
        self.canvas = CanvasWidget(self, shape_limit=6)
        # self.canvas.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        # Add widgets on top of each other
        self.main_layout.addWidget(self.label, 0, 0, 1, 1)
        self.main_layout.addWidget(self.canvas, 0, 0, 1, 1)

        # # Stretch so widget stays in top left
        self.main_layout.setRowStretch(1, 1)
        self.main_layout.setColumnStretch(1, 1)

        # Bring the canvas to the front
        self.canvas.raise_()

    @property
    def video_widget(self) -> VideoWidget:
        return self._video_widget

    @property
    def raw_frame(self) -> np.ndarray | None:
        return self.video_widget.raw_frame

    @property
    def zoom(self) -> float:
        return self.video_widget.zoom

    def minimumSizeHint(self) -> QSize:
        """Define the minimum dimensions of the widget"""
        return QSize(MIN_W, MIN_H)

    def maximumSizeHint(self) -> QSize:
        return QSize(MAX_W, MAX_H)

    def resizeEvent(self, event) -> None:
        """Try to force the widget to stay in the top left corner"""
        super().resizeEvent(event)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        self.label.resize(self.sizeHint())
        self.canvas.resize(self.sizeHint())
        # self.canvas.raise_()
        # print(self.canvas.size(), self.label.size(), self.size())

    def sizeHint(self) -> QSize:
        raw_frame = getattr(self, "raw_frame", None)
        if isinstance(raw_frame, np.ndarray):
            width = int(raw_frame.shape[1] * self.zoom)
            height = int(raw_frame.shape[0] * self.zoom)
            return QSize(width, height)
        else:
            return super().sizeHint()

    @pyqtSlot()
    def force_resize(self) -> None:
        """If the FPS is low, sometimes the display can be unresponsive"""
        pass
        # TODO(ecyoung3): Investigate functionality
        # # Resize the widget
        # self.resize(self.sizeHint())

        # # Resize the image
        # self.label.setPixmap(
        # self.label.pixmap().scaled(self.sizeHint(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        # )


class CameraSettingsWidget(QWidget):
    """A popup widget that shows camera settings"""

    def __init__(self, parent: VideoWidget | None = None, popup: bool = True):
        super().__init__(parent)

        # Make widget open in separate window if "popup" is True
        self.setWindowFlags(Qt.WindowType.Window) if popup else None
        self.setWindowTitle("Edit Camera Settings") if popup else None

        # Settings
        self.setMouseTracking(True)

        # Create status bar for showing status / errors
        self.status_bar = QStatusBar()
        self.status_bar.setSizeGripEnabled(False)
        self.status_bar.setStyleSheet(
            self.status_bar.styleSheet() + "font-style: italic; " + "font-size: 11px; "
        )
        self.status_bar.setContentsMargins(0, 0, 0, 0)

        # Create main layout
        self.main_layout = QGridLayout()
        self.setLayout(self.main_layout)
        self.main_layout.setContentsMargins(8, 8, 8, 8)
        self.main_layout.setSpacing(8)

        # Create label for QComboBox
        self.config_label = QLabel()
        self.config_label.setText("Configuration:")
        self.config_label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)

        # Create QComboBox for selelecting configuration
        self.config_box = QComboBox()
        self.config_box.setToolTip("Select saved settings configuration.")

        # Create button for saving configuration
        self.save_button = QPushButton()
        self.save_button.setText("Save")
        self.save_button.setToolTip("Save current settings configuration.")

        # Create button for deleting configuration
        self.delete_button = QPushButton()
        self.delete_button.setText("Delete")
        self.delete_button.setToolTip("Delete the current settings configuration.")
        self.delete_button.setEnabled(False)

        # Create camera settings widgets (sort alphabetically)
        # TODO(ecyoung3): Move the CameraSettingWidget definition to a different scope
        self._settings_widgets: dict[str, CameraSettingsWidget.CameraSettingWidget] = {}
        row = 2
        for title, info in sorted(self.settings.items(), key=lambda i: i[0]):
            # Create widget
            info["title"] = title
            widget = self.CameraSettingWidget(info, self)
            self._settings_widgets[info["name"]] = widget

            # Add widget to layout
            self.main_layout.addWidget(widget, row, 0, 1, 4)
            row += 1

        # Add the widgets
        self.main_layout.addWidget(self.config_label, 0, 0, 1, 1)
        self.main_layout.addWidget(self.config_box, 0, 1, 1, 1)
        self.main_layout.addWidget(self.save_button, 0, 2, 1, 1)
        self.main_layout.addWidget(self.delete_button, 0, 3, 1, 1)
        self.main_layout.addWidget(HLine(), 1, 0, 1, 4)
        self.main_layout.addWidget(HLine(), row + 2, 0, 1, 4)
        self.main_layout.addWidget(self.status_bar, row + 3, 0, 1, 4)

        # Load the configurations
        self._saved = True
        self._previous_config = self.config_box.currentText()
        self.load_configs()

        # Connect signals
        self.config_box.currentTextChanged.connect(self.set_config)
        self.save_button.clicked.connect(self.save_config)
        self.delete_button.clicked.connect(self.delete_config)

        # Stretch the last row
        self.main_layout.setRowStretch(row + 1, 1)

        # Set fixed size
        width = int(self.sizeHint().width() * 1.5)
        height = self.sizeHint().height()
        self.setFixedSize(width, height)

    @pyqtSlot()
    def show(self) -> None:
        self.setVisible(True)

    @pyqtSlot()
    def hide(self) -> None:
        self.setVisible(False)

    @property
    def camera(self) -> FlirCamera | UsbCamera | None:
        parent = self.parent()
        if type(parent) == VideoWidget:
            return parent.camera
        return None

    @property
    def settings(self) -> dict:
        """Only get read/write-accessible camera settings"""
        if self.camera is None:
            return {}
        settings = getattr(self.camera, "gui_settings", {})
        return {title: self.camera.get_info(name) for name, title in settings.items()}

    @property
    def current_config(self) -> str:
        return self.config_box.currentText()

    @property
    def saved(self) -> bool:
        return self._saved

    @saved.setter
    def saved(self, saved: bool) -> None:
        self._saved = saved
        self.save_button.setEnabled(not saved)

    @pyqtSlot(str)
    def set_config(self, name: str) -> None:
        """Set the current configuration by name"""

        # If current configuration is not saved, prompt user to continue
        if not self._saved and self._previous_config:
            confirm = QMessageBox.question(
                self,
                "Confirm Changing Configuration",
                "Current configuration has not been saved.\n"
                "Would you like to save before switching?",
            )
            if confirm == QMessageBox.StandardButton.Yes:
                self.save_configs()

        # Update previous config
        self._previous_config = self.current_config

        # Get the configuration
        config = self._configs.get(name, None)

        # Return if no configuration is selected
        if config is None:
            self.delete_button.setEnabled(False)
            return
        self.delete_button.setEnabled(True)

        # Set settings widgets to the config values
        for setting, value in config.items():
            widget = self._settings_widgets.get(setting, None)
            if widget is not None:
                widget.set_value(value)

        # Mark as saved
        self.saved = True

        # Set the config box to the selected name
        for idx in range(self.config_box.count()):
            if self.config_box.itemText(idx) == name:
                self.config_box.setCurrentIndex(idx)
                break

    @pyqtSlot()
    def save_config(self) -> None:
        """Save the current configuration"""
        # Get current configuration as a dictionary
        config = self.to_dict()

        # Prompt user to input name
        name, ok = QInputDialog.getText(
            self,
            "Save Configuration",
            "Enter configuration name:",
            QLineEdit.EchoMode.Normal,
            self.current_config,
        )

        # Return if user cancels or rejects the dialog
        if not ok:
            return

        # Make sure a config name is entered
        if not name:
            QMessageBox.warning(self, "Warning", "A configuration name is required.")
            return

        # Make sure the entered config name is unique
        elif name in self._configs:
            action = "update" if name == self.current_config else "overwrite"
            confirm = QMessageBox.question(
                self,
                "Confirm Configuration Name",
                f'A configuration "{name}" already exists.\n' f"Would you like to {action} it?",
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

        # Save configurations
        self._configs[name] = config
        self.save_configs()

        # Reload configurations
        self.load_configs()

        # Switch to the new configuration
        self.set_config(name)

    @pyqtSlot()
    def delete_config(self):
        """Delete the currently selected configuration"""
        # TODO: Prompt before deleting

        # Prompt before deleting
        confirm = QMessageBox.question(self, "Confirm Delete", "Delete this configuration?")
        if confirm != QMessageBox.StandardButton.Yes:
            return

        # Remove the current configuration name
        config = self._configs.pop(self.current_config, None)
        if config is not None:
            self.save_configs()

        # Re-load configurations
        self.load_configs()

    def load_configs(self) -> None:
        """Load configurations from config file"""

        # Load the configuration file
        current_config = self.current_config
        cam_name = getattr(self.camera, "name", "camera")
        try:
            self._configs = utils.load_settings(cam_name)
        except OSError:
            self._configs = {}

        # Clear current items
        self.config_box.clear()

        # Add items to the QComboBox with a blank item at the top
        self.config_box.addItems([""] + list(sorted(self._configs.keys())))

        # Set the current configuration back to what it was
        self.set_config(current_config)

    def save_configs(self) -> None:
        """Save all configurations"""
        utils.save_settings(self._configs, getattr(self.camera, "name", "camera"))
        self.saved = True

    def to_dict(self) -> dict:
        """Represent the current setting configuration as a dictionary"""
        d = {}
        for setting, widget in self._settings_widgets.items():
            d[setting] = widget.get_value()
        return d

    class CameraSettingWidget(QWidget):
        def __init__(self, info: dict[str, Any], parent: CameraSettingsWidget):
            super().__init__(parent)
            self._parent = parent

            # Store info
            self.info = info
            self.name: str = info["name"]
            self.title: str = info["title"]
            self.description: str = info.get("description", "")
            unit = info.get("unit", "")
            self.unit = "µs" if unit == "us" else unit  # fix microsecond formatting
            self.entries = info.get("entries", None)
            self.dtype = info.get("type", None)

            # Get info needed to determine appropriate widget type
            min_val = info.get("min", None)
            max_val = info.get("max", None)
            value = info.get("value", None)

            # Settings
            self.setMouseTracking(True)

            # Create layout
            self.main_layout = QGridLayout()
            self.setLayout(self.main_layout)
            self.main_layout.setContentsMargins(0, 0, 0, 0)
            self.main_layout.setSpacing(4)

            # Use a DoubleSlider if min & max provided
            self.widget: QWidget
            if min_val is not None and max_val is not None:
                # Use log scale if difference between min & max is > 1,000
                log = (max_val / min_val) > 1e3 if min_val != 0 else False
                decimals = max(len(str(min_val).split(".")[-1]), len(str(max_val).split(".")[-1]))
                self.widget = DoubleSlider(decimals, log=log, base=1.5, parent=self)
                self.widget.setMinimum(min_val)
                self.widget.setMaximum(max_val)
                self.widget.setValue(value)
                self.widget.setToolTip(f"minimum = {min_val:,g}, " f"maximum = {max_val:,g}")

            # Create QComboBox for options with listed entries
            elif self.entries is not None or self.dtype == "enum":
                self.widget = QComboBox()
                self.widget.addItems(self.entries)
                self.widget.setCurrentIndex(self.entries.index(value))

            # Create QCheckBox for options with enable/disable
            elif self.dtype == "bool":
                self.widget = QCheckBox()
                self.widget.setChecked(value)
                self.widget.setText(self.title)
                self.widget.setToolTip(self.description)

            # Create QLineEdit for string entries (such as name)
            elif self.dtype == "string":
                self.widget = QLineEdit()
                self.widget.returnPressed.connect(lambda: self.widget.clearFocus())

            else:
                return print(f"Unable to create widget for setting '{info['name']}'")

            # Create label
            self.label: QLabel
            if isinstance(self.widget, QSlider):
                self.label = SliderLabel(self.widget, name=self.title, unit=self.unit, precision=2)
            else:
                self.label = QLabel()
                self.label.setText(f"{self.title}:")
            self.label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
            self.label.setToolTip(self.description.replace(". ", ".\n"))

            # Hide the label if the widget is a QCheckBox since it has a label already
            if isinstance(self.widget, QCheckBox):
                self.label.setVisible(False)

            # Ignore wheel events for non-spinboxes
            self.widget.installEventFilter(self)

            # Set size policy
            self.widget.setSizePolicy(
                QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Maximum
            )

            # Disable the widget if currently inaccessible
            writable = "write" in info.get("access", "write")
            self.widget.setEnabled(writable)
            self.label.setEnabled(writable)

            # Set widget value
            self.set_value(value)

            # Connect signal AFTER setting the value so it doesn't trigger
            self.connect_signal()

            # Add widgets to layout
            self.main_layout.addWidget(self.label, 0, 0, 1, 1)
            self.main_layout.addWidget(self.widget, 0, 1, 1, 1)

        def eventFilter(self, obj: QObject | None, event: QEvent | None) -> bool:
            if type(event) == QWheelEvent:
                if obj == self.widget and not isinstance(obj, QDoubleSpinBox):
                    # Ignore wheel events for non-spinboxes
                    return True
            return False

        def connect_signal(self) -> None:
            if getattr(self, "_connected", False):
                return
            elif isinstance(self.widget, QDoubleSpinBox):
                sig = "valueChanged"
            elif isinstance(self.widget, DoubleSlider):
                sig = "doubleValueChanged"
            elif isinstance(self.widget, QComboBox):
                sig = "currentTextChanged"
            elif isinstance(self.widget, QCheckBox):
                sig = "stateChanged"
            elif isinstance(self.widget, QLineEdit):
                sig = "textChanged"
            else:
                return

            signal: pyqtBoundSignal = getattr(self.widget, sig)
            signal.connect(self.change_setting)
            self._connected = True

        def set_value(self, value: bool | str | float) -> None:
            if isinstance(self.widget, (QDoubleSpinBox, DoubleSlider)) and type(value) == float:
                self.widget.setValue(value)
            elif isinstance(self.widget, QComboBox):
                entries: list[Any] = self.info.get("entries", [])
                self.widget.setCurrentIndex(entries.index(value))
            elif isinstance(self.widget, QCheckBox):
                self.widget.setChecked(bool(value))
            elif isinstance(self.widget, QLineEdit):
                self.widget.setText(str(value))

        def get_value(self) -> bool | str | float:
            """Get the current value of the setting"""
            if isinstance(self.widget, (QDoubleSpinBox, DoubleSlider)):
                return self.widget.value()
            elif isinstance(self.widget, QComboBox):
                return self.widget.currentText()
            elif isinstance(self.widget, QLineEdit):
                return self.widget.text()
            elif isinstance(self.widget, QCheckBox):
                return self.widget.isChecked()
            raise TypeError(f"Widget has unsupported type {type(self.widget)}")

        def change_setting(self, value: bool | str | float) -> None:
            # Mark the SettingsWidget as not saved
            self._parent.saved = False

            value = self.get_value()  # stateChanged emits a bit, not bool
            try:
                setattr(self._parent.camera, self.name, value)

                if isinstance(value, (float, int)):
                    message = f"Successfully set {self.name} to {value:,g}"
                else:
                    message = f"Successfully set {self.name} to {value}"

                if self.unit:
                    message += f" {self.unit}"
            except CameraError as cam_error:
                message = f"Error setting {self.name}: {cam_error}"
            except Exception as ex:
                message = f"Error setting {self.name}: {ex}"
            finally:
                self._parent.status_bar.showMessage(message)
                self._parent.status_bar.setToolTip(message)

            # TODO: Re-check if settings are editable after changing
            # them (e.g. AcquisitionFrameRateEnable)


class CameraStatusBar(QStatusBar):
    def __init__(self, parent: VideoWidget | None = None):
        super().__init__(parent)
        self._parent = parent

        # Disable size grip
        self.setSizeGripEnabled(False)

        # Create widget for displaying FPS
        self.fps_label = QLabel()

        # Add widget for displaying incomplete frame count
        self.incomplete_frames_label = QLabel()
        self.incomplete_frames_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )

        # Add widget for displaying errors
        self.error_label = QLabel()
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # Add widgets
        self.insertWidget(0, self.fps_label, 0)
        self.insertWidget(1, self.incomplete_frames_label, 1)
        self.insertWidget(2, self.error_label, 0)

        # Display status

        # TODO(ecyoung3): Finish implementation
        # # Remove border on widget
        # self.setStyleSheet(self.styleSheet() + """
        #                    QStatusBar::item {border: None;}
        #                    """
        #                    )

    @property
    def camera(self) -> FlirCamera | UsbCamera | None:
        return getattr(self._parent, "camera", None)

    @property
    def fps(self) -> float:
        return getattr(self.camera, "real_fps", 0.0)

    @property
    def incomplete_image_count(self) -> str:
        return str(getattr(self.camera, "incomplete_image_count", ""))

    @property
    def error_status(self) -> str:
        return str(getattr(self.camera, "error_status", "No errors"))

    @pyqtSlot(str)
    def show_error(self, message: str) -> None:
        self.error_label.setText(str(message))

    @pyqtSlot()
    def frame_changed(self) -> None:
        self.fps_label.setText(f"{self.fps:.2f} Hz ")
        self.incomplete_frames_label.setText(f"Incomplete images: {self.incomplete_image_count}")
        self.error_label.setText(self.error_status)


# TODO(ecyoung3): Make this an abstract base class
class Worker(QObject):
    """
    A base class for worker objects.
    https://stackoverflow.com/a/33453124/10342097
    """

    finished = pyqtSignal()
    frame_ready = pyqtSignal(np.ndarray)
    data_ready = pyqtSignal(np.ndarray)
    exception = pyqtSignal(Exception)

    def __init__(self, parent: VideoWidget):
        super().__init__()
        self._parent = parent
        self._running = False

    # TODO(ecyoung3): Make start and stop return boolean indicating success
    def start(self) -> None:
        raise NotImplementedError()

    def stop(self) -> None:
        raise NotImplementedError()

    def camera(self) -> FlirCamera | UsbCamera | None:
        return getattr(self._parent, "camera", None)

    def display(self) -> CameraDisplay | None:
        return getattr(self._parent, "display", None)

    def canvas(self) -> CanvasWidget | None:
        return getattr(self.display(), "canvas", None)

    def running(self) -> bool:
        return self._running


class CameraWorker(Worker):
    """
    A worker object to control frame acquisition.
    """

    @pyqtSlot()
    def start(self) -> None:
        camera = self.camera()
        if camera is None:
            logging.warning("Cannot start CameraWorker if camera is None")
            return

        self._running = True
        while self.running():
            # Emit the next frame
            try:
                if camera.running:
                    self.frame_ready.emit(camera.get_array(complete_frames_only=True))

            # Ignore RuntimeError, for example if the object is deleted
            except RuntimeError:
                pass

            # Emit all other exceptions
            except Exception as ex:
                self.exception.emit(ex)

    @pyqtSlot()
    def stop(self) -> None:
        camera = self.camera()
        if camera is None:
            logging.warning("Cannot stop the CameraWorker if camera is None")
            return
        self._running = False
        camera.close()
        self.finished.emit()


class AnalysisWorker(Worker):
    """
    A worker object to analyze region intensities.
    """

    data_ready = pyqtSignal(dict)

    # TODO(ecyoung3): Make a dataclass for data instances
    data: dict[str, dict[str, Any]] = {}
    start_time: float | None = None

    @property
    def shapes(self) -> list[CanvasShape]:
        return getattr(self.canvas(), "shapes", [])

    @property
    def raw_frame(self) -> np.ndarray | None:
        return getattr(self.camera(), "raw_frame", None)

    @pyqtSlot(np.ndarray)
    def analyze_frame(self, frame: np.ndarray) -> None:
        if not self.running():
            return

        # Get time of data collection relative to start
        if self.start_time is None or len(self.shapes) == 0:
            self.reset_timer()

        if self.start_time is None:
            # This should never happen, but it tells mypy that start_time is a float
            raise TypeError("Somehow start_time is still None after calling reset_timer")

        t = time.time() - self.start_time

        # Get pixel intensities under regions of interest
        for shape in self.shapes:
            # Get the mask
            mask = shape.mask

            # Make sure the mask and frame have the same shape
            if mask.shape != frame.shape:
                continue

            # Extract the data based on the mask region
            data = frame[mask]

            # Store the data
            color = shape.color_name
            if color not in self.data:
                self.data[color] = {
                    "time": [],
                    "sum": [],
                    "average": [],
                    "x": [],
                    "y": [],
                    "image": None,
                    "kind": shape.kind,
                }

            # Store time value
            self.data[color]["time"].append(t)

            # Store line profile
            if shape.kind == "line":
                # self.data[color]["x"].append(np.arange(0, data.size, 1))
                ydata = data.flatten()
                self.data[color]["y"].append(ydata)

                # Make sure line scan image exists
                img = self.data[color]["image"]
                if img is None:
                    # Turn single column into 2D array where 0 is in the bottom left
                    # (assuming starting array like [1, 2, 3, 4, 5, ...])
                    # https://stackoverflow.com/a/44772452/10342097
                    self.data[color]["image"] = column_to_image(ydata)

                # Update line scan data
                else:
                    self.data[color]["image"] = extend_image(img, ydata)

            else:
                # Make sure sum is non-zero to avoid divide-by-zero
                mask_sum = mask.sum()
                if mask_sum != 0:
                    self.data[color]["average"].append(data.sum() / mask_sum)

        self.data_ready.emit(self.data.copy())

    @pyqtSlot()
    def start(self) -> None:
        self._running = True
        self.start_time = time.time()

    @pyqtSlot()
    def stop(self) -> None:
        self._running = False
        self.start_time = None
        self.finished.emit()

    @pyqtSlot()
    def reset(self) -> None:
        self.data = {}
        self.reset_timer()

    @pyqtSlot()
    def reset_timer(self) -> None:
        self.start_time = time.time()


if __name__ == "__main__":

    def test():
        from frheed.utils import test_widget

        camera = FlirCamera(lock=False)
        # camera = UsbCamera(lock=False)
        widget, app = test_widget(VideoWidget, camera=camera, block=True)
        return widget, app

    widget, app = test()

    app.quit()
