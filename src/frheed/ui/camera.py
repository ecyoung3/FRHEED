"""UI components for controlling and displaying images from cameras."""

from __future__ import annotations

import logging

from PyQt6 import QtCore, QtGui, QtMultimedia, QtWidgets

from frheed.ui import colormap, display


class VideoFrameItem(QtWidgets.QGraphicsPixmapItem):
    """A graphics item for displaying a video frame."""

    def __init__(self, parent: QtWidgets.QGraphicsItem | None = None) -> None:
        super().__init__(parent)
        self._colormap: str | None = None

    def get_colormap(self) -> str | None:
        """Returns the name of the active colormap."""
        return self._colormap

    def set_colormap(self, cmap_name: str | None) -> None:
        """Sets the active colormap to a matplotlib colormap with the given name."""
        self._colormap = cmap_name

    def get_colortable(self) -> list[int] | None:
        """The colortable to apply to frames before setting them."""
        if (cmap := self.get_colormap()) is None:
            return None

        return colormap.get_colortable(cmap)

    def set_frame(self, frame: QtMultimedia.QVideoFrame) -> None:
        """Sets the given video frame to be displayed."""
        # Get the frame image and convert to 8-bit grayscale if necessary
        image = frame.toImage()
        if not image.isGrayscale():
            image = image.convertToFormat(QtGui.QImage.Format.Format_Grayscale8)

        # Apply the current colormap if one is set
        if (colortable := self.get_colortable()) is not None:
            image = image.convertToFormat(QtGui.QImage.Format.Format_Indexed8)
            image.setColorTable(colortable)

        # Convert the image to a pixmap and show it on the display
        pixmap = QtGui.QPixmap.fromImage(image)
        self.setPixmap(pixmap)


class CameraDisplay(display.Display):
    """A display for showing live video from a camera and interactively drawing shapes over it."""

    # Signal emitted when the active camera changes
    camera_changed = QtCore.pyqtSignal()

    def __init__(
        self, camera: QtMultimedia.QCamera | None = None, parent: QtWidgets.QWidget | None = None
    ) -> None:
        # Create the image item to display camera images, the media capture session to store the
        # images, and the video sink to transmit the images, but *not* the camera itself since it
        # requires the display to have been initialized first.
        self._video_frame_item = VideoFrameItem()
        self._camera: QtMultimedia.QCamera | None = None
        self._session = QtMultimedia.QMediaCaptureSession()
        self._video_sink = QtMultimedia.QVideoSink()
        self._video_sink.videoFrameChanged.connect(self._video_frame_item.set_frame)
        self._session.setVideoSink(self._video_sink)

        super().__init__(self._video_frame_item, parent)
        self.set_camera(camera)

    @property
    def video_frame_item(self) -> VideoFrameItem:
        """The item used to display video frames."""
        return self._video_frame_item

    @QtCore.pyqtSlot(QtMultimedia.QCamera.Error, str)
    def on_camera_error_occurred(self, error: QtMultimedia.QCamera.Error, msg: str) -> None:
        """Handles a camera error."""
        if error == QtMultimedia.QCamera.Error.NoError:
            return

        # TODO(ecyoung3): Display the error somewhere in the UI
        logging.error("A camera error occurred: %s", msg)

    def get_camera(self) -> QtMultimedia.QCamera | None:
        """Returns the active camera."""
        return self._camera

    def set_camera(self, camera: QtMultimedia.QCamera | None = None) -> None:
        """Sets the active camera.

        If a different camera is already active, it will be disconnected and replaced.
        """
        if camera == (current_camera := self.get_camera()):
            if camera is not None:
                camera_description = camera.cameraDevice().description()
                logging.warning("Requested camera %r is already active", camera_description)

            return

        # Stop the current camera before releasing and replacing it
        if current_camera is not None:
            logging.info("Stopping camera %r", current_camera.cameraDevice().description())
            current_camera.stop()

        self._camera = camera
        self._session.setCamera(camera)

        # Clear the current image before returning if no camera is set
        if camera is None:
            # TODO(ecyoung3): Identify the best way to indicate there is no camera connected
            self.video_frame_item.hide()
            return

        # Start the camera with its maximum resolution by default
        if camera_formats := camera.cameraDevice().videoFormats():
            # The largest resolution format (native format) is listed last
            native_format = camera_formats[-1]
            resolution = native_format.resolution()
            logging.info(
                "Setting camera format to %sx%s resolution and pixel format %r",
                resolution.width(),
                resolution.height(),
                native_format.pixelFormat().name,
            )
            camera.setCameraFormat(native_format)

            # Resize the display to perfectly fit the video frame
            self.resize(resolution)

        # Start the camera if it's not already active
        if camera is not None and not camera.isActive():
            logging.info("Starting camera %r", camera.cameraDevice().description())
            camera.start()

        # Make sure the image is visible if no camera was set previously
        self.video_frame_item.show()

        # Only notify that the camera was changed after everything is complete
        self.camera_changed.emit()

    def set_default_camera(self) -> None:
        """Sets the camera to the system default."""
        if (default_device := QtMultimedia.QMediaDevices.defaultVideoInput()).isNull():
            logging.warning("No cameras found")
            return

        logging.info("Setting default camera %r", default_device.description())
        default_camera = QtMultimedia.QCamera(default_device)
        self.set_camera(default_camera)

    def get_resolution(self) -> QtCore.QSize | None:
        """Returns the resolution of the active camera."""
        if (camera := self.get_camera()) is None:
            return None

        return camera.cameraFormat().resolution()

    def get_colormap(self) -> str | None:
        """Returns the name of the active colormap."""
        return self.video_frame_item.get_colormap()

    def set_colormap(self, cmap_name: str | None) -> None:
        """Sets the active colormap."""
        self.video_frame_item.set_colormap(cmap_name)


class CameraWidget(QtWidgets.QWidget):
    """A widget for controlling, capturing, and displaying live video from a camera."""

    def __init__(
        self, camera: QtMultimedia.QCamera | None = None, parent: QtWidgets.QWidget | None = None
    ) -> None:
        super().__init__(parent)

        self.menubar = QtWidgets.QMenuBar(self)
        self.menubar.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.MinimumExpanding, QtWidgets.QSizePolicy.Policy.Maximum
        )

        self.colormap_menu = colormap.ColormapFamiliesMenu()
        self.colormap_menu.colormap_selected.connect(self.set_colormap)
        self.menubar.addMenu(self.colormap_menu)

        # If no camera is provided, attempt to connect to the default
        self.camera_display = CameraDisplay(camera, self)
        if camera is None:
            self.camera_display.set_default_camera()

        layout = QtWidgets.QGridLayout(self)
        layout.setSpacing(2)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.menubar, 0, 0, 1, 1)
        layout.addWidget(self.camera_display, 1, 0, 1, 1)

        if (camera_resolution := self.camera_display.get_resolution()) is not None:
            self.resize(camera_resolution)
        else:
            self.resize(640, 480)

    @QtCore.pyqtSlot()
    def on_camera_changed(self) -> None:
        # TODO(ecyoung3): Implement
        pass

    def set_default_camera(self) -> None:
        """Sets the camera to the system default."""
        self.camera_display.set_default_camera()

    def get_colormap(self) -> str | None:
        """Returns the name of the active colormap."""
        return self.camera_display.get_colormap()

    def set_colormap(self, cmap_name: str | None) -> None:
        """Sets the active colormap."""
        self.camera_display.set_colormap(cmap_name)
