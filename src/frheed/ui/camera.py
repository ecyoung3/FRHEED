"""UI components for controlling and displaying images from cameras."""

from __future__ import annotations

import logging

from PyQt6 import QtCore, QtGui, QtMultimedia, QtWidgets

from frheed.ui import colormap, display


class ImageEmitter(QtCore.QObject):
    """Emits images on behalf of instances that do not derive from QObject."""

    image_changed = QtCore.pyqtSignal(QtGui.QImage)


class VideoFrameItem(QtWidgets.QGraphicsPixmapItem):
    """A graphics item for displaying a video frame."""

    def __init__(self, parent: QtWidgets.QGraphicsItem | None = None) -> None:
        super().__init__(parent)
        self._colormap: str | None = None

        # Because this class does not inherit from QObject, it cannot emit signals on its own, so
        # we must use a helper class instance to emit images
        self._image_emitter = ImageEmitter()

        # Store grayscale and colored copies of the frame to minimize conversion operations
        # TODO(ecyoung3): Implement this storage
        self._grayscale_image: QtGui.QImage | None = None
        self._colored_image: QtGui.QImage | None = None

    @property
    def image_changed(self) -> QtCore.pyqtBoundSignal:
        return self._image_emitter.image_changed

    def get_colormap(self) -> str | None:
        """Returns the name of the active colormap."""
        return self._colormap

    def set_colormap(self, cmap_name: str | None) -> None:
        """Sets the active colormap to a matplotlib colormap with the given name."""
        # Interpret empty strings as `None` because emitting `None` from a signal actually sends an
        # empty string to the signal, not literal `None`
        if cmap_name == "":
            cmap_name = None

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

        # Apply the current colormap if one is set
        if (colortable := self.get_colortable()) is not None:
            # Convert to grayscale before applying the colormap, otherwise performance is very slow
            if not image.isGrayscale():
                image = image.convertToFormat(QtGui.QImage.Format.Format_Grayscale8)

            # Convert the image to indexed 8-bit without changing the format
            if image.reinterpretAsFormat(QtGui.QImage.Format.Format_Indexed8):
                image.setColorTable(colortable)

        # Convert the image to a pixmap and show it on the display
        pixmap = QtGui.QPixmap.fromImage(image)
        self.setPixmap(pixmap)

        # Send the image to any connected slots
        self.image_changed.emit(image)


class CameraDisplay(display.Display):
    """A display for showing live video from a camera and interactively drawing shapes over it."""

    # Signal emitted when the active camera changes
    camera_changed = QtCore.pyqtSignal(QtMultimedia.QCamera)

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
            self.camera_changed.emit(None)
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
        self.camera_changed.emit(camera)

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


class CameraSelectionAction(QtGui.QAction):
    """An action used to select a camera."""

    def __init__(
        self,
        camera: QtMultimedia.QCamera | None,
        group: QtGui.QActionGroup,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        """Initializes the camera selection action."""
        if camera is not None:
            title = camera.cameraDevice().description()
        else:
            title = "No camera"

        super().__init__(title, parent)

        self.setCheckable(True)
        self.setActionGroup(group)
        self.setData(camera)
        self._camera = camera

    def get_camera(self) -> QtMultimedia.QCamera | None:
        """Returns the camera associated with this action."""
        return self._camera

    def get_camera_id(self) -> QtCore.QByteArray | None:
        """Returns the ID of the camera associated with this action."""
        if (camera := self.get_camera()) is None:
            return None

        return camera.cameraDevice().id()


class CameraSelectionMenu(QtWidgets.QMenu):
    """A menu for selecting a camera."""

    # Signal emitted when a camera is selected
    camera_selected = QtCore.pyqtSignal(QtMultimedia.QCamera)

    def __init__(self, title: str = "&Cameras", parent: QtWidgets.QWidget | None = None) -> None:
        """Initializes the menu with the list of all available cameras."""
        super().__init__(title, parent)

        # Store menu items in an exclusive group since only one camera should be selected at a time
        self._action_group = QtGui.QActionGroup(self)
        self._action_group.setExclusive(True)

        # Emit the `camera_selected` signal when an action is triggered
        self.triggered.connect(self.on_action_triggered)

        # Refresh the menu when the list of available cameras changes
        self._media_devices_watcher = QtMultimedia.QMediaDevices()
        self._media_devices_watcher.videoInputsChanged.connect(self.refresh_cameras)

        # Populate the menu
        self.refresh_cameras()

    @QtCore.pyqtSlot(QtGui.QAction)
    def on_action_triggered(self, action: QtGui.QAction) -> None:
        """Emits the camera associated with the selected action."""
        if isinstance(action, CameraSelectionAction):
            self.camera_selected.emit(action.get_camera())
        else:
            logging.warning(
                "Triggered action %r is not a camera selection action: %r", action.text(), action
            )

    @QtCore.pyqtSlot(QtMultimedia.QCamera)
    def on_camera_changed(self, camera: QtMultimedia.QCamera | None) -> None:
        """Updates the checked state of each menu item when a camera is selected elsewhere."""
        camera_id = None if camera is None else camera.cameraDevice().id()
        for action in self._action_group.actions():
            if isinstance(action, CameraSelectionAction):
                # Check the action if its camera was selected, otherwise uncheck the item
                action.setChecked(action.get_camera_id() == camera_id)

    def refresh_cameras(self) -> None:
        """Refreshes the menu with the list of available cameras."""
        # Clear the current actions from both the menu and the action group
        self.clear()
        for action in self._action_group.actions():
            self._action_group.removeAction(action)

        if not (devices := self._media_devices_watcher.videoInputs()):
            # No available devices to choose from
            logging.warning("No available cameras detected")
            return

        # Repopulate the menu with actions for each of the currently-available video input devices
        for device in devices:
            logging.info("Found available camera: %s", device.description())
            camera = QtMultimedia.QCamera(device)
            action = CameraSelectionAction(camera, self._action_group, self)
            self.addAction(action)


class CameraWidget(QtWidgets.QWidget):
    """A widget for controlling, capturing, and displaying live video from a camera."""

    def __init__(
        self, camera: QtMultimedia.QCamera | None = None, parent: QtWidgets.QWidget | None = None
    ) -> None:
        super().__init__(parent)

        # Create the camera display first so signals and slots can be connected to it
        self.camera_display = CameraDisplay(camera, self)
        self.camera_display.camera_changed.connect(self.on_camera_changed)

        # TODO(ecyoung3): Clean up this connection
        self.camera_display._video_frame_item.image_changed.connect(self.on_image_changed)

        # Create the menu bar with menus for selecting the camera and colormap
        self.menubar = QtWidgets.QMenuBar(self)
        self.menubar.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.MinimumExpanding, QtWidgets.QSizePolicy.Policy.Maximum
        )

        self.camera_selection_menu = CameraSelectionMenu(parent=self)
        self.camera_display.camera_changed.connect(self.camera_selection_menu.on_camera_changed)
        self.camera_selection_menu.camera_selected.connect(self.camera_display.set_camera)
        self.menubar.addMenu(self.camera_selection_menu)

        self.colormap_selection_menu = colormap.ColormapSelectionMenu.for_all_colormaps(parent=self)
        self.colormap_selection_menu.colormap_selected.connect(self.camera_display.set_colormap)
        self.menubar.addMenu(self.colormap_selection_menu)

        # Create the layout and add widgets to it
        layout = QtWidgets.QGridLayout(self)
        layout.setSpacing(2)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.menubar, 0, 0, 1, 1)
        layout.addWidget(self.camera_display, 1, 0, 1, 1)

        if (camera_resolution := self.camera_display.get_resolution()) is not None:
            self.resize(camera_resolution)
        else:
            self.resize(1280, 960)

    @QtCore.pyqtSlot()
    def on_camera_changed(self) -> None:
        # TODO(ecyoung3): Implement
        pass

    @QtCore.pyqtSlot(QtGui.QImage)
    def on_image_changed(self, image: QtGui.QImage | None) -> None:
        if image is None:
            return

        for shape in self.camera_display.shapes:
            region = display.get_image_region(image, shape)

            try:
                print(
                    f"{region.sum() = }, {region.mean() = }, {region.min() = }, {region.max() = }"
                )
                # print(f"{region = }")
            except ValueError:
                # Array is empty
                pass
