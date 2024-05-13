"""GUI components for displaying and drawing shapes over images."""

import collections
import enum
import itertools
import logging

import PyQt6.QtCore as QtCore
import PyQt6.QtGui as QtGui
import PyQt6.QtWidgets as QtWidgets

# Displayable shape types
Shape = QtWidgets.QGraphicsRectItem | QtWidgets.QGraphicsEllipseItem | QtWidgets.QGraphicsLineItem

# Colorblind-friendly color scheme
HEX_COLORS = (
    "#E69F00",  # light orange
    "#56B4E9",  # light blue
    "#009E73",  # blueish green
    "#F0E442",  # yellow
    "#0072B2",  # deeper blue
    "#D55E00",  # deeper orange
    "#CC79A7",  # pink
)


class ShapeTransformMode(enum.Enum):
    """A mode of transforming a shape shown on an interactive display."""

    TRANSLATE = enum.auto()
    MOVE_TOP_LEFT = enum.auto()
    MOVE_TOP_RIGHT = enum.auto()
    MOVE_BOTTOM_RIGHT = enum.auto()
    MOVE_BOTTOM_LEFT = enum.auto()
    MOVE_TOP = enum.auto()
    MOVE_RIGHT = enum.auto()
    MOVE_BOTTOM = enum.auto()
    MOVE_LEFT = enum.auto()


class InteractiveDisplay(QtWidgets.QGraphicsView):
    """A graphics view for displaying images and interactively drawing shapes over them."""

    # Shapes should be drawn without fill by default
    _DEFAULT_BRUSH = QtGui.QBrush(QtCore.Qt.BrushStyle.NoBrush)

    # The types of shapes that can be drawn
    _SHAPE_TYPES: tuple[type[Shape], ...] = (
        QtWidgets.QGraphicsRectItem,
        QtWidgets.QGraphicsEllipseItem,
        QtWidgets.QGraphicsLineItem,
    )

    # The minimum width and height of a shape, in pixels
    _MIN_SHAPE_SIZE = 10

    # Default linewidth for shapes
    _DEFAULT_LINEWIDTH = 2

    # Linewidth for focused shape
    _FOCUSED_LINEWIDTH = 4

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        # Create a graphics scene that is always displayed in the top left of the view
        self._scene = QtWidgets.QGraphicsScene()
        self.setScene(self._scene)
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignLeft)

        # Zoom on the mouse rather than the top left of the scene
        self.setTransformationAnchor(QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse)

        # Create the graphics item for displaying images; it should always be the lowermost item
        self._image_item = QtWidgets.QGraphicsPixmapItem()
        self._scene.addItem(self._image_item)

        # Rectangles, ellipses, and lines that are drawn on the graphics scene
        self._shapes: list[Shape] = []

        # The type of shape to draw
        self._shape_types_cycle = itertools.cycle(self._SHAPE_TYPES)
        self.next_shape_type()

        # The color of shape to draw
        self._available_colors = collections.deque(HEX_COLORS)

        # The index of the currently selected shape, which can be moved or resized
        self._current_shape_idx: int | None = None

        # The origin of the mouse click, if currently moving or resizing a shape
        self._first_click_pos: QtCore.QPointF | None = None

    def mouseMoveEvent(self, event: QtGui.QMouseEvent | None) -> None:
        if event is None:
            return

        if self.current_shape is None:
            # No event is currently selected; use default event handling
            super().mouseMoveEvent(event)
        elif self._first_click_pos is None:
            # Shape is selected but not being resized; determine if the mouse is nearby
            # TODO(ecyoung3): Implement edge proximity detection
            pass
        else:
            # Shape is being transformed
            # TODO(ecyoung3): Transform shape based on transformation mode
            pass

    def mousePressEvent(self, event: QtGui.QMouseEvent | None) -> None:
        if event is None:
            return

        if event.button() == QtCore.Qt.MouseButton.MiddleButton:
            # Reset the scale when pressing the middle mouse button
            event.accept()
            logging.info("Pressed middle mouse button; resetting interactive display scale")
            self.resetTransform()
        elif event.button() == QtCore.Qt.MouseButton.RightButton:
            if event.modifiers() == QtCore.Qt.KeyboardModifier.NoModifier:
                # Cycle the active shape when pressing the right mouse button with no modifiers
                event.accept()
                logging.info(
                    "Pressed right mouse button; cycling shape (current index = %s)",
                    self._current_shape_idx,
                )
                self.next_shape()
            elif event.modifiers() == QtCore.Qt.KeyboardModifier.ControlModifier:
                # Cycle the shape type when pressing the right mouse button while control is pressed
                event.accept()
                logging.info("Cycling shape type (currently %s)", self._current_shape_type.__name__)
                self.next_shape_type()
        elif event.button() == QtCore.Qt.MouseButton.LeftButton:
            if event.modifiers() == QtCore.Qt.KeyboardModifier.NoModifier:
                # Pressed left click with no keyboard modifiers
                if self.current_shape is None:
                    # No shape is currently selected; begin adding a new one
                    pos = event.scenePosition()
                    self._first_click_pos = pos
                    x1 = pos.x()
                    y1 = pos.y()
                    x2 = x1 + self._MIN_SHAPE_SIZE
                    y2 = y1 + self._MIN_SHAPE_SIZE
                    self.add_shape(x1, y1, x2, y2)
                else:
                    # A shape is currently selected; determine if it is nearby to begin modifying it
                    # TODO(ecyoung3): Implement determination of transformation mode
                    pass
        else:
            super().mousePressEvent(event)

    def wheelEvent(self, event: QtGui.QWheelEvent | None) -> None:
        if event is None:
            return

        if event.modifiers() == QtCore.Qt.KeyboardModifier.ControlModifier:
            # Only scale if CTRL is pressed while scrolling
            if (dy := event.angleDelta().y()) != 0:
                # Only scale the scene if the mouse is scrolled up or down (not left or right)
                event.accept()
                if dy > 0:
                    # Zoom in when scrolling upwards
                    self.scale(1.03, 1.03)
                else:
                    # Zoom out when scrolling downwards
                    self.scale(0.97, 0.97)
        else:
            # Use default event handling if CTRL is not pressed
            super().wheelEvent(event)

    @property
    def current_shape(self) -> Shape | None:
        if self._current_shape_idx is None:
            return None

        return self._shapes[self._current_shape_idx]

    def set_image(self, image: QtGui.QImage) -> None:
        """Sets the displayed image."""
        pixmap = QtGui.QPixmap.fromImage(image)
        self._image_item.setPixmap(pixmap)

    def add_shape(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
    ) -> Shape | None:
        """Adds a new shape of the currently-selected type to the display."""
        # Determine if a new shape can be added
        if not self._available_colors:
            logging.warning("The maximum number of shapes (%s) already exist", len(HEX_COLORS))
            return None

        # Create a pen with the current color and linewidth for drawing the rectangle
        hex_color = self._available_colors.popleft()
        color = QtGui.QColor(hex_color)
        pen = QtGui.QPen(color)
        pen.setWidth(self._DEFAULT_LINEWIDTH)

        # Do not change the pen width when scaling the rectangle
        pen.setCosmetic(True)

        # Attempt to draw the shape on the scene
        w = x2 - x1
        h = y2 - y1
        match self._current_shape_type:
            case QtWidgets.QGraphicsRectItem:
                shape = self._scene.addRect(x1, y1, w, h, pen, self._DEFAULT_BRUSH)
            case QtWidgets.QGraphicsEllipseItem:
                shape = self._scene.addEllipse(x1, y1, w, h, pen, self._DEFAULT_BRUSH)
            case QtWidgets.QGraphicsLineItem:
                shape = self._scene.addLine(x1, y1, x2, y2, pen)
            case _:
                raise TypeError("Unsupported shape type '%s'", self._current_shape_type)

        if shape is None:
            raise ValueError(
                f"Failed to add shape of type '{self._current_shape_type}' "
                f"with {x1 = }, {y1 = }, {x2 = }, {y2 = }"
            )

        self._shapes.append(shape)
        return shape

    def next_shape(self) -> None:
        """Cycles to the next shape in chronological order of creation."""
        if not self._shapes:
            # No shapes exist, thus nothing to cycle
            return

        # Reset the linewidth of the current shape
        if self.current_shape is not None:
            # Updating the pen in-place will not cause the scene to re-paint; need to re-set the pen
            pen = self.current_shape.pen()
            pen.setWidth(self._DEFAULT_LINEWIDTH)
            self.current_shape.setPen(pen)

        # Select the next shape
        if self._current_shape_idx is None:
            # Select the first shape if none is currently selected
            self._current_shape_idx = 0
        elif self._current_shape_idx == len(self._shapes) - 1:
            # Select no shape if the last shape is currently selected
            self._current_shape_idx = None
        else:
            # Select the next shape if one is currently selected that is not the last shape
            self._current_shape_idx += 1

        # Update the linewidth of the newly-selected shape
        if self.current_shape is not None:
            pen = self.current_shape.pen()
            pen.setWidth(self._FOCUSED_LINEWIDTH)
            self.current_shape.setPen(pen)

    def next_shape_type(self) -> None:
        """Cycles to the next shape type."""
        self._current_shape_type = next(self._shape_types_cycle)
