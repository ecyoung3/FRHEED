"""
PyQt widgets for drawing shapes.
"""

from __future__ import annotations

import abc
import enum
from collections.abc import Iterator

import numpy as np
from PyQt6.QtCore import (
    QLineF,
    QObject,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    QSize,
    QSizeF,
    Qt,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtGui import (
    QAction,
    QActionGroup,
    QColor,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
    QResizeEvent,
)
from PyQt6.QtWidgets import QApplication, QLabel, QMenu, QMessageBox, QWidget

from frheed.constants import COLOR_DICT
from frheed.utils import get_qcolor

DEFAULT_COLOR = list(COLOR_DICT.values())[0]
DEFAULT_LINEWIDTH = 1
FOCUSED_LINEWIDTH = 2
EDGE_PAD = 8
MIN_SHAPE_SIZE = 10


# https://stackoverflow.com/a/2233538/10342097
def line_point_dist(line: QLineF, point: QPointF) -> float:
    """Calculate the shortest distance between a QLine and a QPoint"""

    # Convert coordinates to float
    x1, x2, y1, y2 = (line.x1(), line.x2(), line.y1(), line.y2())
    px, py = (point.x(), point.y())
    dx, dy = (line.dx(), line.dy())

    # Calculate norm
    norm = dx**2 + dy**2

    # If norm == 0, return 0
    if norm == 0:
        return 0.0

    # Calculate slope
    u = ((px - x1) * dx + (py - y1) * dy) / norm
    u = 1 if u > 1 else 0 if u < 0 else u

    # Calculate relative coordinates
    rel_x = x1 + u * dx
    rel_y = y1 + u * dy

    # Calculate X and Y separation
    sep_x = rel_x - px
    sep_y = rel_y - py

    # Calculate distance
    dist = np.sqrt(sep_x**2 + sep_y**2)
    return dist


class ShapeType(enum.Enum):
    RECTANGLE = enum.auto()
    ELLIPSE = enum.auto()
    LINE = enum.auto()


class ShapeRegion(enum.Flag):
    """A region near a shape."""

    NOT_NEARBY = enum.auto()
    # Line regions
    P1 = enum.auto()
    P2 = enum.auto()
    CENTER = enum.auto()
    NEAR_LINE = P1 | P2 | CENTER
    # Rectangle regions
    TOP = enum.auto()
    BOTTOM = enum.auto()
    LEFT = enum.auto()
    RIGHT = enum.auto()
    TOP_LEFT = enum.auto()
    TOP_RIGHT = enum.auto()
    BOTTOM_LEFT = enum.auto()
    BOTTOM_RIGHT = enum.auto()
    NEAR_EDGE = TOP | BOTTOM | LEFT | RIGHT
    NEAR_CORNER = TOP_LEFT | TOP_RIGHT | BOTTOM_LEFT | BOTTOM_RIGHT
    NEAR_RECT = NEAR_EDGE | NEAR_CORNER
    # Ellipse regions
    TOP_MIDDLE = TOP | enum.auto()
    BOTTOM_MIDDLE = BOTTOM | enum.auto()
    LEFT_MIDDLE = LEFT | enum.auto()
    RIGHT_MIDDLE = RIGHT | enum.auto()
    NEAR_ELLIPSE = TOP_MIDDLE | BOTTOM_MIDDLE | LEFT_MIDDLE | RIGHT_MIDDLE


CURSOR_SHAPE_BY_SHAPE_REGION: dict[ShapeRegion, Qt.CursorShape] = {
    ShapeRegion.P1: Qt.CursorShape.OpenHandCursor,
    ShapeRegion.P2: Qt.CursorShape.OpenHandCursor,
    ShapeRegion.CENTER: Qt.CursorShape.SizeAllCursor,
    ShapeRegion.LEFT: Qt.CursorShape.SizeHorCursor,
    ShapeRegion.RIGHT: Qt.CursorShape.SizeHorCursor,
    ShapeRegion.TOP: Qt.CursorShape.SizeVerCursor,
    ShapeRegion.BOTTOM: Qt.CursorShape.SizeVerCursor,
    ShapeRegion.TOP_LEFT: Qt.CursorShape.SizeFDiagCursor,
    ShapeRegion.BOTTOM_RIGHT: Qt.CursorShape.SizeFDiagCursor,
    ShapeRegion.TOP_RIGHT: Qt.CursorShape.SizeBDiagCursor,
    ShapeRegion.BOTTOM_LEFT: Qt.CursorShape.SizeBDiagCursor,
}


class CanvasWidget(QLabel):
    """A widget for drawing shapes."""

    shape_deleted = pyqtSignal(object)

    def __init__(self, parent: QWidget | None = None, shape_limit: int = 10) -> None:
        super().__init__(parent)
        self._shape_limit = shape_limit

        # Enable mouse tracking so it can detect mouseEvent
        self.setMouseTracking(True)

        # Enable context menus
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        # Create context menu
        self.menu = QMenu(self)
        self.clear_canvas_action = QAction("&Clear shapes", self)
        self.menu.addAction(self.clear_canvas_action)
        self.menu.addSeparator()

        # Create submenu for selecting shape
        self.shape_type_menu = QMenu(title="&Select shape type")
        self.menu.addMenu(self.shape_type_menu)
        self.shape_action_group = QActionGroup(self.menu)
        for shape_type in ShapeType:
            action = QAction(f"&{shape_type.name.title()}", self)
            action.setCheckable(True)
            action.setChecked(shape_type == ShapeType.RECTANGLE)
            action.setActionGroup(self.shape_action_group)
            self.shape_type_menu.addAction(action)

        # Set minimum size
        self.setMinimumSize(QSize(3, 3))

        # Create transparent pixmap
        pixmap = QPixmap(self.size())
        pixmap.fill(QColor("transparent"))
        self.setPixmap(pixmap)

        # Attributes to be assigned later
        self._drawing: bool = False
        self._draw_start_pos: QPoint | None = None
        self._resizing: bool = False
        self._resizing_from: str | None = None
        self._moving: bool = False
        self._move_start_pos: QPoint | None = None
        self._shapes: list[CanvasShape] = []
        self._active_shape: CanvasShape | None = None
        self._pressed_buttons: list[int] = []

        # Connect signals
        self.customContextMenuRequested.connect(self.menu_requested)
        self.clear_canvas_action.triggered.connect(self.clear_canvas)

    # TODO(ecyoung3): Move these events to eventFilter.
    def resizeEvent(self, event: QResizeEvent | None) -> None:
        """Resize all shapes when the canvas is resized."""
        super().resizeEvent(event)
        if event is None:
            return

        # Resize the shapes
        old, new = event.oldSize(), self.size()
        for shape in self.shapes:
            shape.rescale(old, new)

    def keyPressEvent(self, event: QKeyEvent | None) -> None:
        super().keyPressEvent(event)
        if event is None:
            return

        # Delete active shape when "Delete" key is pressed
        if event.key() == Qt.Key.Key_Delete:
            if self.active_shape is not None:
                self.active_shape.delete()

                # Restore the mouse cursor
                QApplication.restoreOverrideCursor()

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        super().mousePressEvent(event)
        if event is None:
            return

        # Left button events
        if event.button() == Qt.MouseButton.LeftButton:
            # Drawing should not start if another shape is active
            if self.active_shape is None:
                self._draw_start_pos = event.pos().toPointF()

            # Indicate that resizing has started if a shape is active
            elif isinstance(self.active_shape, (CanvasRect, CanvasEllipse)):
                if self.active_shape.nearest_region(event.pos()) == ShapeRegion.CENTER:
                    self.moving = True
                    self._move_start_pos = self.active_shape.p1() - event.pos()
                else:
                    self.resizing = True
                    self._resizing_from = self.active_shape.nearest_region(event.pos())

        # Right button events
        elif event.button() == Qt.MouseButton.RightButton:
            # QApplication.setOverrideCursor(Qt.ArrowCursor)
            QApplication.restoreOverrideCursor()

        # Middle button events
        elif event.button() == Qt.MouseButton.MiddleButton:
            # Indicate that shape movement can start
            if self.active_shape is not None:
                self.moving = True
                if isinstance(self.active_shape, CanvasShape):
                    self._move_start_pos = self.active_shape.topLeft() - event.pos()
                elif isinstance(self.active_shape, CanvasLine):
                    self._move_start_pos = self.active_shape.p1() - event.pos()

    def mouseReleaseEvent(self, event: QMouseEvent | None = None) -> None:
        # Left button events
        if event.button() == Qt.MouseButton.LeftButton:
            self._draw_start_pos = None
            self.drawing = False
            self.resizing = False

            # If moving a line, stop
            if self.moving and not self.drawing:
                self.moving = False
                self._move_start_pos = None

        # Right button events
        elif event.button() == Qt.MouseButton.RightButton:
            # Restore cursor if not drawing, moving, or resizing
            if not (self.drawing or self.moving or self.resizing):
                QApplication.setOverrideCursor(Qt.CursorShape.ArrowCursor)
                # QApplication.restoreOverrideCursor()
                return

        # Middle button events
        elif event.button() == Qt.MouseButton.MiddleButton:
            self.moving = False
            self._move_start_pos = None

        # Normalize all shapes
        [shape.normalize() for shape in self.shapes]
        self.draw()

        # Re-check the override cursor if released mouse is not right mouse
        if self.active_shape is not None and event.button() != Qt.MouseButton.RightButton:
            region = self.active_shape.nearest_region(event.pos())
            if (cursor_shape := CURSOR_SHAPE_BY_SHAPE_REGION.get(region)) is not None:
                QApplication.setOverrideCursor(cursor_shape)
        else:
            QApplication.restoreOverrideCursor()

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:
        super().mouseMoveEvent(event)

        # Get the event position
        pos = event.pos().toPointF()

        # Start drawing if mouse has moved > 10 pixels while LMB pressed
        if self.can_draw:
            x1, y1 = self._draw_start_pos.x(), self._draw_start_pos.y()
            x2, y2 = pos.x(), pos.y()
            sep = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
            if sep > MIN_SHAPE_SIZE:
                self.drawing = True
                self.add_shape(self._draw_start_pos)

        # Expand the active shape if one is being drawn
        if self.active_shape is not None and self.drawing:
            if self.active_shape.kind in [ShapeType.RECTANGLE, ShapeType.ELLIPSE]:
                self.active_shape.resize("bottom_right", pos)
            elif self.active_shape.kind == ShapeType.LINE:
                self.active_shape.resize("p2", pos)

        # Resize shape
        elif self.active_shape is not None and self.resizing:
            self.active_shape.resize(self.resizing_from, pos)

        # Move shape
        elif self.active_shape is not None and self.moving:
            x = pos.x() + self._move_start_pos.x()
            y = pos.y() + self._move_start_pos.y()
            self.active_shape.moveTo(QPoint(x, y))
            self.active_shape.update()

        # If no shape is active and not drawing, moving, or resizing
        else:
            # Detect which shape (if any) is near the cursor
            for shape in self.shapes:
                # Activate the shape (increase border width)
                if shape.point_nearby(pos):
                    shape.activate()

                    # Set cursor style
                    region = shape.nearest_region(pos)
                    if (cursor_shape := CURSOR_SHAPE_BY_SHAPE_REGION.get(region)) is not None:
                        QApplication.setOverrideCursor(cursor_shape)

                # Deactivate shapes not near the cursor
                else:
                    shape.deactivate()

        # If the LMB is pressed and the cursor is an open hand,
        # make the cursor a closed hand
        cursor = QApplication.overrideCursor()
        if cursor is not None and self.button_pressed(Qt.MouseButton.LeftButton):
            if cursor.shape() == Qt.CursorShape.OpenHandCursor:
                QApplication.setOverrideCursor(Qt.CursorShape.ClosedHandCursor)

        if self.active_shape is None:
            QApplication.restoreOverrideCursor()

    @property
    def shape_type(self) -> ShapeType:
        shape_type_name = self.shape_action_group.checkedAction().text().strip("&")
        return ShapeType[shape_type_name.upper()]

    @property
    def shape_limit(self) -> int:
        return self._shape_limit

    @shape_limit.setter
    def shape_limit(self, limit: int) -> None:
        self._shape_limit = limit
        if len(self.shapes) > self._shape_limit:
            # Keep the oldest shapes
            self._shapes = self._shapes[: self._shape_limit]
            self.draw()

    @property
    def can_draw(self) -> bool:
        return (
            self._draw_start_pos is not None
            and self.button_pressed(Qt.MouseButton.LeftButton)
            and not self.drawing
            and self.active_shape is None
            and not self.resizing
        )

    @property
    def drawing(self) -> bool:
        return self._drawing

    @drawing.setter
    def drawing(self, drawing: bool) -> None:
        self._drawing = drawing

    @property
    def resizing(self) -> bool:
        return self._resizing

    @resizing.setter
    def resizing(self, resizing: bool) -> None:
        self._resizing = resizing
        self._resizing_from = None

    @property
    def resizing_from(self) -> str | None:
        return self._resizing_from

    @property
    def moving(self) -> bool:
        return self._moving

    @moving.setter
    def moving(self, moving: bool) -> None:
        self._moving = moving

        # Update the mouse cursor
        if moving:
            QApplication.setOverrideCursor(Qt.CursorShape.SizeAllCursor)
        else:
            QApplication.restoreOverrideCursor()

    @property
    def shapes(self) -> list[CanvasShape]:
        return self._shapes

    @shapes.setter
    def shapes(self, shapes: list[CanvasShape]) -> None:
        self._shapes = shapes
        self.active_shape = None
        self.draw()

    @property
    def active_shape(self) -> CanvasShape | None:
        return self._active_shape

    @active_shape.setter
    def active_shape(self, shape: CanvasShape) -> None:
        self._active_shape = shape

        # Deactivate other shapes so only one can be active at once
        for other_shape in self.shapes:
            if shape is other_shape:
                continue
            other_shape.deactivate()

        # Restore mouse cursor if no active shapes
        if self._active_shape is None:
            QApplication.restoreOverrideCursor()

    @pyqtSlot(QPoint)
    def menu_requested(self, p: QPoint) -> None:
        """Show the right-click popup menu"""
        # Ignore right click while drawing, moving or resizing
        if self.drawing or self.moving or self.resizing:
            return

        # Show the menu
        self.menu.popup(self.mapToGlobal(p))

    def button_pressed(self, button: Qt.MouseButton) -> bool:
        return bool(button & int(QApplication.mouseButtons()))

    def add_shape(self, pos: QPoint) -> CanvasShape:
        """Add a shape to the canvas at the given point."""

        # Make sure the shape limit has not been hit
        if len(self.shapes) >= self.shape_limit:
            self.drawing = False
            msg = f"Maximum of {self.shape_limit} regions of interest allowed."
            QMessageBox.information(self, "Notice", msg)
            return None

        # Define initial shape dimensions
        x, y, w, h = pos.x(), pos.y(), 0, 0

        # Create the shape or line
        if self.shape_type in (ShapeType.RECTANGLE, ShapeType.ELLIPSE):
            shape = CanvasRect(x, y, w, h)
            shape.kind = self.shape_type

        elif self.shape_type == ShapeType.LINE:
            shape = CanvasLine(x, y, x, y)

        # Get the next color
        color_idx = len(self.shapes) % (len(COLOR_DICT) + 1)
        shape.color = list(COLOR_DICT.values())[color_idx]

        # Assign the canvas to the shape
        shape.canvas = self

        # Activate the shape, which will also draw it
        shape.activate()

        return shape

    def draw(self) -> None:
        """Redraw all the shapes"""

        # Get a fresh pixmap
        pixmap = QPixmap(self.size())
        pixmap.fill(QColor("transparent"))

        # Get a fresh painter
        painter = QPainter(pixmap)

        # Set the pen
        pen = QPen()
        pen.setCosmetic(True)
        painter.setPen(pen)

        # Draw each of the shapes
        for shape in self.shapes:
            # Set pen properties
            pen.setColor(shape.color)
            pen.setWidthF(shape.linewidth)
            painter.setPen(pen)

            # Draw the shape
            if shape.kind == ShapeType.RECTANGLE:
                painter.drawRect(shape)
            elif shape.kind == ShapeType.ELLIPSE:
                painter.drawEllipse(shape)
            elif shape.kind == ShapeType.LINE:
                painter.drawLine(shape)

        # !!!IMPORTANT!!! End the painter otherwise the GUI will crash
        painter.end()

        # Update the pixmap
        self.setPixmap(pixmap)

    @pyqtSlot()
    def clear_canvas(self) -> None:
        """Clear all shapes and reset the canvas"""
        # Use the delete function so signals are properly emitted
        # Can't use list comprehension because size of list will change during iteration
        while self.shapes:
            self.shapes[0].delete()


class CanvasShape(abc.ABC):
    """Base class for shapes that can be drawn on a canvas.
    
    All coordinates follow the [Qt coordinate system](https://doc.qt.io/qt-6/coordsys.html) where
    (0, 0) is the top left corner of the canvas the shape is drawn on.
    """

    @property
    @abc.abstractmethod
    def canvas(self) -> CanvasWidget:
        """The canvas to draw the shape on."""

    @abc.abstractmethod
    def get_color(self) -> QColor:
        """Returns the color of the shape."""

    @abc.abstractmethod
    def set_color(self, color: QColor) -> None:
        """Sets the color of the shape."""

    @abc.abstractmethod
    def get_linewidth(self) -> int:
        """Returns the width in pixels of the shape's lines."""

    @abc.abstractmethod
    def set_linewidth(self, linewidth: int) -> None:
        """Sets the width in pixels of the shape's lines."""

    @abc.abstractmethod
    def get_coordinates(self) -> tuple[float, float, float, float]:
        """Returns the shape's coordinates (x1, y1, x2, y2) relative to the canvas origin.
        
        The top left corner of the shape is (x1, y1), and the bottom right corner is (x2, y2).
        """

    @abc.abstractmethod
    def set_coordinates(self, x1: float, y1: float, x2: float, y2: float) -> None:
        """Sets the top left corner of the shape to (x1, y1) and the bottom right to (x2, y2)."""

    @abc.abstractmethod
    def scale(self, factor: float) -> None:
        """Scale the shape by the given factor."""

    @abc.abstractmethod
    def as_mask(self) -> np.ndarray:
        """Returns a mask of the canvas pixels covered by the shape."""

    @abc.abstractmethod
    def point_distance_from_region(self, point: QPointF, region: ShapeRegion) -> float:
        """Returns the distance from a point to a region of the shape."""
        # TODO(ecyoung3): Implement
        raise NotImplementedError()

    @abc.abstractmethod
    def nearby_regions(self, point: QPointF) -> Iterator[ShapeRegion]:
        """Yields all regions that are near a point."""

    @abc.abstractmethod
    def nearest_region(self, point: QPointF) -> ShapeRegion:
        """Returns which region of the shape is closest to a point."""

    @abc.abstractmethod
    def move_to(self, pos: QPointF) -> None:
        """Move the shape to a new position."""

    @property
    def is_active(self) -> bool:
        """Whether or not the shape is active on its canvas."""
        return self.canvas is not None and self.canvas.active_shape == self

    def constrain_to_canvas(self, point: QPointF) -> QPointF:
        """Make sure a point falls within the canvas dimensions."""
        x = max(0, min(self.canvas.width() - self.linewidth, point.x()))
        y = max(0, min(self.canvas.height() - self.linewidth, point.y()))
        return QPointF(x, y)

    def update(self) -> None:
        """Redraw this shape (and all others) on the parent canvas"""
        self.canvas.draw()

    def delete(self) -> None:
        """Remove the shape from the associated canvas"""
        self.canvas.shape_deleted.emit(self)
        self.canvas.shapes.remove(self)
        self.deactivate()

    @pyqtSlot()
    def activate(self) -> None:
        self.linewidth = FOCUSED_LINEWIDTH
        if self.canvas is not None:
            self.canvas.active_shape = self
        self.update()

    @pyqtSlot()
    def deactivate(self) -> None:
        if self.is_active and self.canvas is not None:
            self.canvas.active_shape = None
        self.linewidth = DEFAULT_LINEWIDTH
        self.update()


class CanvasLine(CanvasShape):
    """A line that can be drawn on a canvas."""

    def __init__(self, canvas: CanvasWidget, shape: QLineF) -> None:
        self.canvas = canvas
        self.shape = shape

    def get_coordinates(self) -> tuple[float, float, float, float]:
        return (self.shape.x1(), self.shape.y1(), self.shape.x2(), self.shape.y2())

    def set_coordinates(self, x1: float, y1: float, x2: float, y2: float) -> None:
        self.shape.setLine(x1, y1, x2, y2)

    def moveTo(self, p1: QPointF) -> None:
        """Move the line's p1 to a new point"""

        # Get new coordinates
        new_p2 = QPointF(p1.x() + self.dx(), p1.y() + self.dy())

        # Validate coordinates
        if self.canvas is not None:
            new_line = QLineF(p1, new_p2)
            x1, y1, x2, y2 = (new_line.x1(), new_line.y1(), new_line.x2(), new_line.y2())
            xmin, xmax = sorted([x1, x2])
            ymin, ymax = sorted([y1, y2])
            width, height = self.canvas.width(), self.canvas.height()
            lw = self.linewidth
            if xmin < 0 or ymin < 0 or xmax > (width - lw) or ymax > (height - lw):
                return

        # Move the line and update the canvas
        self.setPoints(p1, new_p2)
        self.update()

    def normalize(self) -> None:
        """This doesn't do anything but is provided since CanvasShape has it"""

    def width(self) -> float:
        """Make sure width is always positive"""
        return abs(super().dx())

    def height(self) -> float:
        """Make sure height is always positive"""
        return abs(super().dy())

    @property
    def canvas(self) -> CanvasWidget:
        return self._canvas

    @canvas.setter
    def canvas(self, canvas: CanvasWidget) -> None:
        self._canvas = canvas
        self._canvas._shapes.append(self)

    @property
    def color(self) -> QColor | None:
        return self._color

    @color.setter
    def color(self, color: str | tuple | QColor) -> None:
        self._color = get_qcolor(color)

    @property
    def color_name(self) -> str | None:
        if self.color is None:
            return None
        return self.color.name()

    @property
    def linewidth(self) -> int:
        return self._linewidth

    @linewidth.setter
    def linewidth(self, linewidth: int) -> None:
        self._linewidth = linewidth
        self.update()

    @property
    def active(self) -> bool:
        if self.canvas is None:
            return False
        return self.canvas.active_shape is self

    def dist_from_point(self, point: QPointF) -> float:
        return line_point_dist(self, point)

    def point_nearby(self, point: QPointF) -> bool:
        """Determine if a point is near the line"""
        return self.dist_from_point(point) < EDGE_PAD

    def dist_from_p1(self, point: QPointF) -> float:
        """Get the distance from a point to p1 of the line"""
        return np.sqrt((point.x() - self.x1()) ** 2 + (point.y() - self.y1()) ** 2)

    def near_p1(self, point: QPointF) -> bool:
        """Determine if a point is near p1 of the line"""
        return self.dist_from_p1(point) < EDGE_PAD

    def dist_from_p2(self, point: QPointF) -> float:
        """Get the distance from a point to p2 of the line"""
        return np.sqrt((point.x() - self.x2()) ** 2 + (point.y() - self.y2()) ** 2)

    def near_p2(self, point: QPointF) -> bool:
        """Determine if a point is near p2 of the line"""
        return self.dist_from_p2(point) < EDGE_PAD

    def dist_from_center(self, point: QPointF) -> float:
        return self.dist_from_point(point)

    def near_center(self, point: QPointF) -> bool:
        """Determine if a point is near the line (excluding the ends)"""
        return self.point_nearby(point) and not (self.near_p1(point) or self.near_p2(point))

    def nearby_regions(self, point: QPointF) -> Iterator[ShapeRegion]:
        """Get a list of regions that are near a point"""
        # TODO(ecyoung3): Also streamline this logic if possible
        if self.near_p1(point):
            yield ShapeRegion.P1
        if self.near_p2(point):
            yield ShapeRegion.P2
        if self.near_center(point):
            yield ShapeRegion.CENTER

    def nearest_region(self, point: QPointF) -> ShapeRegion:
        """Determine which region of the line is closest to the point"""
        regions = list(self.nearby_regions(point))
        if not regions:
            return ShapeRegion.NOT_NEARBY
        elif len(regions) == 1:
            # Return region if it's the only one nearby
            return regions[0]
        else:
            # Determine which region is closest if there are multiple
            # TODO(ecyoung3): This needs to return a ShapeRegion instead
            seps = [(r, getattr(self, f"dist_from_{str(r.name).lower()}")(point)) for r in regions]

            # Get the name of the nearest region
            return sorted(seps, key=lambda i: i[1])[0][0]

    @property
    def mask(self) -> np.ndarray:
        """
        Get a numpy mask where pixels on the line = True.
        https://stackoverflow.com/a/44874588/10342097
        """

        # Get dimensions of canvas if it exists, otherwise line dimensions
        if self.canvas is None:
            width, height = self.width(), self.height()
        else:
            size = self.canvas.size()
            width, height = size.width(), size.height()

        # Create full array of False values with the proper size
        mask = np.full((height, width), False, dtype=bool)

        # Get endpoints
        x1, y1, x2, y2 = self.getCoords()
        x1, x2 = sorted([x1, x2])
        y1, y2 = sorted([y1, y2])

        # Create linspace of points along the X and Y dimensions
        num = int(max(self.width(), self.height()) * 10)  # this can probably be optimized
        x = np.linspace(int(min(x1, width - 1)), int(min(x2, width - 1)), num, endpoint=False)
        y = np.linspace(int(min(y1, height - 1)), int(min(y2, height - 1)), num, endpoint=False)

        # Mask values along the line
        mask[y, x] = True
        return mask

    def rescale(self, old: QSize, new: QSize) -> None:
        """Scale the line when the canvas changes"""

        # Get the scale factors
        w0, h0 = old.width(), old.height()
        w1, h1 = new.width(), new.height()
        w_scale, h_scale = (w1 / max(w0, 1)), (h1 / max(h0, 1))

        # Rescale the shape
        x1, y1, x2, y2 = self.getCoords()
        x1_new, x2_new = (x1 * w_scale), (x2 * w_scale)
        y1_new, y2_new = (y1 * h_scale), (y2 * h_scale)
        self.setCoords(x1_new, y1_new, x2_new, y2_new)
        self.update()

    def resize(self, region: ShapeRegion, point: QPointF) -> None:
        """Resize the line using the mouse"""
        p = self.constrain_to_canvas(point)

        if region == ShapeRegion.P1:
            self.setP1(point)
        elif region == ShapeRegion.P2:
            self.setP2(point)

        self.update()


class CanvasRect(QRectF, CanvasShape):
    """A rectangle that can be drawn on a canvas."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._kind = ShapeType.RECTANGLE
        self._color = get_qcolor(DEFAULT_COLOR)

        # Attributes to be assigned later
        self._linewidth: int = DEFAULT_LINEWIDTH
        self._canvas: CanvasWidget | None = None

    def moveTo(self, p: QPointF) -> None:  # type: ignore[override]
        """Move the top left corner to point 'p'"""

        # Make sure the resulting position is valid
        if self.canvas is not None:
            new_shape = QRectF(p.x(), p.y(), self.width(), self.height())
            x1, y1, x2, y2 = new_shape.getCoords()
            if x1 is None or y1 is None or x2 is None or y2 is None:
                raise ValueError("Somehow the new QRectF coordinates are not set")

            width, height = self.canvas.width(), self.canvas.height()
            lw = self.linewidth
            if x1 < 0 or y1 < 0 or x2 > (width - lw) or y2 > (height - lw):
                return

        # Move the shape
        super().moveTo(p)
        self.update()

    def get_coords(self) -> tuple[float, float, float, float]:
        """Returns the bounding coordinates (x1, y1, x2, y2) for the rectangle."""
        x1, y1, x2, y2 = self.getCoords()

        # NOTE: Written this way so mypy downcasts types for each coord from float | None -> float
        if x1 is None or y1 is None or x2 is None or y2 is None:
            raise ValueError(f"CanvasRect coordinates are not fully set: ({x1}, {y1}, {x2}, {y2})")

        return (x1, y1, x2, y2)

    def normalize(self) -> None:
        """Normalize the shape so it has non-negative width/height"""

        top_left, bottom_left = self.topLeft(), self.bottomLeft()
        top_right, bottom_right = self.topRight(), self.bottomRight()

        if self.width() < 0:
            self.setTopRight(top_left)
            self.setTopLeft(top_right)
            self.setBottomRight(bottom_left)
            self.setBottomLeft(bottom_right)

        top_left, bottom_left = self.topLeft(), self.bottomLeft()
        top_right, bottom_right = self.topRight(), self.bottomRight()

        if self.height() < 0:
            self.setTopRight(bottom_right)
            self.setTopLeft(bottom_left)
            self.setBottomRight(top_right)
            self.setBottomLeft(top_left)

    @property
    def kind(self) -> ShapeType:
        return self._kind

    @kind.setter
    def kind(self, kind: ShapeType) -> None:
        self._kind = kind
        self.update()

    @property
    def color(self) -> QColor | None:
        return self._color

    @color.setter
    def color(self, color: str | tuple | QColor) -> None:
        self._color = get_qcolor(color)

    @property
    def color_name(self) -> str | None:
        if self.color is None:
            return None
        return self.color.name()

    @property
    def linewidth(self) -> int:
        return self._linewidth

    @linewidth.setter
    def linewidth(self, linewidth: int) -> None:
        self._linewidth = linewidth
        self.update()

    @property
    def active(self) -> bool:
        return getattr(self.canvas, "active_shape", self) == self

    @property
    def top_left_region(self) -> tuple:
        """Top left corner bounding box (xmin, ymin, xmax, ymax)"""
        x1, y1, _, _ = self.get_coords()
        return ((x1 - EDGE_PAD), (y1 - EDGE_PAD), (x1 + EDGE_PAD), (y1 + EDGE_PAD))

    def near_top_left(self, p: QPointF) -> bool:
        xmin, ymin, xmax, ymax = self.top_left_region
        return (xmin < p.x() < xmax) and (ymin < p.y() < ymax)

    def dist_from_top_left(self, p: QPointF) -> float:
        """Get the distance from a point to the top left corner"""
        return np.sqrt((self.top() - p.y()) ** 2 + (self.left() - p.x()) ** 2)

    @property
    def top_right_region(self) -> tuple:
        """Top right corner bounding box (xmin, ymin, xmax, ymax)"""
        _, y1, x2, _ = self.get_coords()
        return ((x2 - EDGE_PAD), (y1 - EDGE_PAD), (x2 + EDGE_PAD), (y1 + EDGE_PAD))

    def near_top_right(self, p: QPointF) -> bool:
        xmin, ymin, xmax, ymax = self.top_right_region
        return (xmin < p.x() < xmax) and (ymin < p.y() < ymax)

    def dist_from_top_right(self, p: QPointF) -> float:
        """Get the distance from a point to the top right corner"""
        return np.sqrt((self.top() - p.y()) ** 2 + (self.right() - p.x()) ** 2)

    @property
    def bottom_left_region(self) -> tuple:
        """Bottom left corner bounding box (xmin, ymin, xmax, ymax)"""
        x1, _, _, y2 = self.get_coords()
        return ((x1 - EDGE_PAD), (y2 - EDGE_PAD), (x1 + EDGE_PAD), (y2 + EDGE_PAD))

    def near_bottom_left(self, p: QPointF) -> bool:
        xmin, ymin, xmax, ymax = self.bottom_left_region
        return (xmin < p.x() < xmax) and (ymin < p.y() < ymax)

    def dist_from_bottom_left(self, p: QPointF) -> float:
        """Get the distance from a point to the bottom left corner"""
        return np.sqrt((self.bottom() - p.y()) ** 2 + (self.left() - p.x()) ** 2)

    @property
    def bottom_right_region(self) -> tuple:
        """Bottom right corner bounding box (xmin, ymin, xmax, ymax)"""
        _, _, x2, y2 = self.get_coords()
        return ((x2 - EDGE_PAD), (y2 - EDGE_PAD), (x2 + EDGE_PAD), (y2 + EDGE_PAD))

    def near_bottom_right(self, point: QPointF) -> bool:
        xmin, ymin, xmax, ymax = self.bottom_right_region
        return (xmin < point.x() < xmax) and (ymin < point.y() < ymax)

    def dist_from_bottom_right(self, p: QPointF) -> float:
        """Get the distance from a point to the bottom left corner"""
        return np.sqrt((self.bottom() - p.y()) ** 2 + (self.right() - p.x()) ** 2)

    @property
    def left_region(self) -> tuple:
        """Left region bounding box (xmin, ymin, xmax, ymax)"""
        x1, y1, _, y2 = self.get_coords()
        return ((x1 - EDGE_PAD), (y1 + EDGE_PAD), (x1 + EDGE_PAD), (y2 - EDGE_PAD))

    def near_left(self, p: QPointF) -> bool:
        xmin, ymin, xmax, ymax = self.left_region
        return (xmin < p.x() < xmax) and (ymin < p.y() < ymax)

    def dist_from_left(self, p: QPointF) -> float:
        """Get the distance from a point to the left edge"""
        return abs(p.x() - self.left())

    @property
    def right_region(self) -> tuple:
        """Right region bounding box (xmin, ymin, xmax, ymax)"""
        _, y1, x2, y2 = self.get_coords()
        xmin, xmax = (x2 - EDGE_PAD), (x2 + EDGE_PAD)
        ymin, ymax = (y1 + EDGE_PAD), (y2 - EDGE_PAD)
        return (xmin, ymin, xmax, ymax)

    def near_right(self, p: QPointF) -> bool:
        xmin, ymin, xmax, ymax = self.right_region
        return (xmin < p.x() < xmax) and (ymin < p.y() < ymax)

    def dist_from_right(self, point: QPointF) -> float:
        """Get the distance from a point to the right edge"""
        return abs(point.x() - self.right())

    @property
    def bottom_region(self) -> tuple:
        """Bottom region bounding box (xmin, ymin, xmax, ymax)"""
        x1, _, x2, y2 = self.get_coords()
        xmin, xmax = (x1 + EDGE_PAD), (x2 - EDGE_PAD)
        ymin, ymax = (y2 - EDGE_PAD), (y2 + EDGE_PAD)
        return (xmin, ymin, xmax, ymax)

    def near_bottom(self, p: QPointF) -> bool:
        xmin, ymin, xmax, ymax = self.bottom_region
        return (xmin < p.x() < xmax) and (ymin < p.y() < ymax)

    def dist_from_bottom(self, p: QPointF) -> float:
        """Get the distance from a point to the bottom edge"""
        return abs(p.y() - self.bottom())

    @property
    def top_region(self) -> tuple:
        """Top region bounding box (xmin, ymin, xmax, ymax)"""
        x1, y1, x2, _ = self.get_coords()
        xmin, xmax = (x1 + EDGE_PAD), (x2 - EDGE_PAD)
        ymin, ymax = (y1 - EDGE_PAD), (y1 + EDGE_PAD)
        return (xmin, ymin, xmax, ymax)

    def near_top(self, point: QPointF) -> bool:
        xmin, ymin, xmax, ymax = self.top_region
        return (xmin < point.x() < xmax) and (ymin < point.y() < ymax)

    def dist_from_top(self, point: QPointF) -> float:
        """Get the distance from a point to the top edge"""
        return abs(point.y() - self.top())

    def point_nearby(self, point: QPointF) -> bool:
        """Check if a QPoint is near any border of the shape"""
        return any(
            (
                self.near_top(point),
                self.near_bottom(point),
                self.near_left(point),
                self.near_right(point),
            )
        )

    def nearby_regions(self, point: QPointF) -> Iterator[ShapeRegion]:
        """Get list of regions that are near a point"""
        # TODO(ecyoung3): There has to be a better way of doing this...
        if self.near_top(point):
            yield ShapeRegion.TOP
        if self.near_bottom(point):
            yield ShapeRegion.BOTTOM
        if self.near_left(point):
            yield ShapeRegion.LEFT
        if self.near_right(point):
            yield ShapeRegion.RIGHT
        if self.near_top_left(point):
            yield ShapeRegion.TOP_LEFT
        if self.near_top_right(point):
            yield ShapeRegion.TOP_RIGHT
        if self.near_bottom_left(point):
            yield ShapeRegion.BOTTOM_LEFT
        if self.near_bottom_right(point):
            yield ShapeRegion.BOTTOM_RIGHT

    def nearest_region(self, point: QPointF) -> ShapeRegion:
        """Determine which region of the shape is closest to the point"""

        # Get list of nearby regions
        regions = list(self.nearby_regions(point))
        if not regions:
            return ShapeRegion.NOT_NEARBY

        # Return region if only one is nearby
        elif len(regions) == 1:
            return regions[0]

        # Need to determine which region is closest if there are multiple
        else:
            # Get distances from the point to each region
            # TODO(ecyoung3): This needs to return ShapeRegion instead
            seps = [(r, getattr(self, f"dist_from_{r}")(point)) for r in regions]

            # Get the name of the nearest region
            return sorted(seps, key=lambda i: i[1])[0][0]

    @property
    def mask(self) -> np.ndarray:
        """
        Get a numpy mask where pixels inside the shape = True.
        https://stackoverflow.com/a/44874588/10342097
        """
        # Get dimensions of canvas if it exists, otherwise the shape dimensions
        # TODO(ecyoung3): Verify that this is creating the correct mask
        if self.canvas is None:
            width, height = int(self.width()), int(self.height())
        else:
            size = self.canvas.size()
            width, height = size.width(), size.height()

        # Get the center of the shape
        center = self.center()
        h, k = center.x(), center.y()

        # Get the shape dimensions, avoiding divide-by-zero error
        x1, y1, x2, y2 = self.get_coords()
        a = max(abs(x2 - x1) / 2, 1)
        b = max(abs(y2 - y1) / 2, 1)

        # Create the mask by calculating which pixels fall inside the shape
        if self.kind == ShapeType.RECTANGLE:
            mask = np.full((height, width), False, dtype=bool)
            mask[int(y1) : int(y2 + 1), int(x1) : int(x2 + 1)] = True
        elif self.kind == ShapeType.ELLIPSE:
            # Equation for ellipse: ((x - h)^2 / a^2) + ((y - k)^2 / b^2) = 1
            # with center (h, k) and horizontal/vertical radii (a, b)
            Y, X = np.ogrid[:height, :width]
            mask = (((X - h) ** 2 / (a**2)) + ((Y - k) ** 2 / (b**2))) <= 1
        else:
            raise ValueError(f"Unknown shape type {self.kind}")

        return mask

    def rescale(self, old: QSizeF, new: QSizeF) -> None:
        """Scale the shape when the canvas changes"""

        # Get the scale factors
        w0, h0 = old.width(), old.height()
        w1, h1 = new.width(), new.height()
        w_scale, h_scale = (w1 / max(w0, 1)), (h1 / max(h0, 1))

        # Work in floating point to avoid rounding problems
        x1, y1, x2, y2 = self.get_coords()
        x1_new, x2_new = (x1 * w_scale), (x2 * w_scale)
        y1_new, y2_new = (y1 * h_scale), (y2 * h_scale)

        # Rescale the shape
        self.setCoords(x1_new, y1_new, x2_new, y2_new)
        self.update()

    def resize(self, region: ShapeRegion, pos: QPointF) -> None:
        """Resize the shape by moving a region to a new position."""
        pos = self.constrain_to_canvas(pos)

        if region == ShapeRegion.LEFT:
            self.setLeft(pos.x())
        elif region == ShapeRegion.RIGHT:
            self.setRight(pos.x())
        elif region == ShapeRegion.TOP:
            self.setTop(pos.y())
        elif region == ShapeRegion.BOTTOM:
            self.setBottom(pos.y())
        elif region == ShapeRegion.TOP_LEFT:
            self.setTopLeft(pos)
        elif region == ShapeRegion.TOP_RIGHT:
            self.setTopRight(pos)
        elif region == ShapeRegion.BOTTOM_LEFT:
            self.setBottomLeft(pos)
        elif region == ShapeRegion.BOTTOM_RIGHT:
            self.setBottomRight(pos)

        self.update()


if __name__ == "__main__":

    def test():
        import sys

        from PyQt6.QtWidgets import QApplication

        from frheed.utils import test_widget

        app = QApplication.instance() or QApplication([])
        widget, app = test_widget(CanvasWidget, block=False, parent=None)
        sys.exit(app.exec())

    test()
