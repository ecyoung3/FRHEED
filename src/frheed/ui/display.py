"""UI components for displaying and drawing shapes over images."""

from __future__ import annotations

import enum
import itertools
import logging

import attrs
from PyQt6 import QtCore, QtGui, QtWidgets

from frheed import image_util

# The default pen width for all shapes
SHAPE_PEN_WIDTH = 2

# The pen width for shapes that have focus
FOCUS_PEN_WIDTH = 4

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


class ShapeHandleLocation(enum.Enum):
    """The visual location of a shape handle relative to its associated shape."""

    TOP_LEFT = enum.auto()
    TOP_MIDDLE = enum.auto()
    TOP_RIGHT = enum.auto()
    MIDDLE_RIGHT = enum.auto()
    BOTTOM_RIGHT = enum.auto()
    BOTTOM_MIDDLE = enum.auto()
    BOTTOM_LEFT = enum.auto()
    MIDDLE_LEFT = enum.auto()


class Shape(QtWidgets.QGraphicsPathItem):
    """A shape that can be interactively drawn on a display."""

    _HANDLE_LOCATIONS: tuple[ShapeHandleLocation, ...] = (
        ShapeHandleLocation.TOP_LEFT,
        ShapeHandleLocation.TOP_MIDDLE,
        ShapeHandleLocation.TOP_RIGHT,
        ShapeHandleLocation.MIDDLE_RIGHT,
        ShapeHandleLocation.BOTTOM_RIGHT,
        ShapeHandleLocation.BOTTOM_MIDDLE,
        ShapeHandleLocation.BOTTOM_LEFT,
        ShapeHandleLocation.MIDDLE_LEFT,
    )

    def __init__(
        self,
        p1: QtCore.QPointF,
        p2: QtCore.QPointF,
        color: QtGui.QColor,
        parent: QtWidgets.QGraphicsPixmapItem,
        use_bounding_box: bool = True,
    ) -> None:
        super().__init__(parent)

        # Attributes for properties
        self._parent_image_item = parent
        self._handle_by_logical_location: dict[ShapeHandleLocation, ShapeHandle] = {}
        self._bounding_box: ShapeBoundingBox | None = None

        # Draw the shape without updating the bounding box, which does not exist yet
        self.set_points(p1, p2)

        # Make the shape focusable and send geometry changes so that its movement can be restricted
        # to the area of the parent image item
        self.setFlags(
            QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsFocusable
            | QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )

        # Draw the shape with the given color and default line width, and make the pen cosmetic such
        # that its width does not change when scaling the shape or view
        pen = QtGui.QPen(color)
        pen.setWidthF(SHAPE_PEN_WIDTH)
        pen.setCosmetic(True)
        self.setPen(pen)

        # Leave the center of the shape transparent
        self.setBrush(QtGui.QBrush(QtCore.Qt.BrushStyle.NoBrush))

        # Create the bounding rectangle to help with shape resizing
        if use_bounding_box:
            self._bounding_box = ShapeBoundingBox(self)
            self._bounding_box.hide()

        # Create all the shape handles
        for location in self._HANDLE_LOCATIONS:
            self._handle_by_logical_location[location] = ShapeHandle(self, location)

    @QtCore.pyqtSlot(QtGui.QFocusEvent)
    def focusInEvent(self, event: QtGui.QFocusEvent | None) -> None:
        """Show the bounding rectangle item for a shape"""
        super().focusInEvent(event)
        self.set_pen_width(FOCUS_PEN_WIDTH)
        if self.bounding_box is not None:
            self.bounding_box.show()

        # Make sure handles are in the right position before showing them
        self.update_handle_positions()
        for handle in self.handles:
            handle.show()

    @QtCore.pyqtSlot(QtGui.QFocusEvent)
    def focusOutEvent(self, event: QtGui.QFocusEvent | None) -> None:
        super().focusOutEvent(event)
        self.set_pen_width(SHAPE_PEN_WIDTH)
        if self.bounding_box is not None:
            self.bounding_box.hide()

        for handle in self.handles:
            handle.hide()

    @QtCore.pyqtSlot(QtWidgets.QGraphicsItem.GraphicsItemChange, QtCore.QPointF)
    def itemChange(
        self, change: QtWidgets.QGraphicsItem.GraphicsItemChange, top_left_delta: QtCore.QPointF
    ) -> QtCore.QPointF:
        position_change = QtWidgets.QGraphicsItem.GraphicsItemChange.ItemPositionChange
        if change == position_change and self.scene() is not None:
            # Get what the new top left position would be after the item change and constrain it so
            # that no part of the shape would fall outside the parent image after the change
            bounding_rect = self.get_bounding_rect()
            current_top_left = bounding_rect.topLeft()
            new_top_left = self._constrain_to_image(current_top_left + top_left_delta)

            # Convert back to a delta from the current position
            top_left_delta = new_top_left - current_top_left

        return top_left_delta

    def paint(
        self,
        painter: QtGui.QPainter | None,
        option: QtWidgets.QStyleOptionGraphicsItem | None,
        widget: QtWidgets.QWidget | None = None,
    ) -> None:
        # Remove the dotted line that is drawn by default to indicate focus
        # https://stackoverflow.com/a/57505618/10342097
        if option is not None:
            option.state &= ~QtWidgets.QStyle.StateFlag.State_Selected

        super().paint(painter, option, widget)

    @property
    def p1(self) -> QtCore.QPointF:
        return self._p1

    @property
    def p2(self) -> QtCore.QPointF:
        return self._p2

    @property
    def bounding_box(self) -> ShapeBoundingBox | None:
        return self._bounding_box

    @property
    def handles(self) -> list[ShapeHandle]:
        return list(self._handle_by_logical_location.values())

    def _draw_shape(self, p1: QtCore.QPointF, p2: QtCore.QPointF) -> None:
        """Draws the shape."""
        raise NotImplementedError("Not implemented on the base class; use a subclass instead")

    def _constrain_to_image(self, top_left: QtCore.QPointF) -> QtCore.QPointF:
        """Constrains a top left position so that no part of the shape is outside the image."""
        # Get the position relative to the parent image item
        bounding_rect = self.get_bounding_rect()

        # Get the coordinates in which to constrain the shape
        parent_rect = self._parent_image_item.boundingRect().normalized()
        min_x = parent_rect.left()
        max_x = parent_rect.right()
        min_y = parent_rect.top()
        max_y = parent_rect.bottom()

        # Constrain the shape to the parent image
        top_left.setX(min(max_x - bounding_rect.width(), max(min_x, top_left.x())))
        top_left.setY(min(max_y - bounding_rect.height(), max(min_y, top_left.y())))

        return top_left

    def set_pen_width(self, width: float) -> None:
        """Sets the pen width for drawing the shape."""
        pen = self.pen()
        pen.setWidthF(width)
        self.setPen(pen)

    def set_points(
        self,
        p1: QtCore.QPointF,
        p2: QtCore.QPointF,
    ) -> None:
        """Sets the positions of p1 and p2 for the shape."""
        # Need to use the _pre_-normalized corner positions for p1 and p2, otherwise lines will
        # always be drawn from top left to bottom right (rectangles and ellipses appear the same)
        self._p1 = p1
        self._p2 = p2
        self._draw_shape(p1, p2)
        self.update_bounding_box()
        self.update_handle_positions()

    def move_to(self, pos: QtCore.QPointF) -> None:
        """Translates the shape such that its top left corner is at the given position."""
        top_left_delta = pos - self.get_bounding_rect().topLeft()
        p1 = self.p1 + top_left_delta
        p2 = self.p2 + top_left_delta
        self.set_points(p1, p2)

    def get_bounding_rect(self) -> QtCore.QRectF:
        """Returns a rectangle representing the geometric extent of this shape."""
        return QtCore.QRectF(self.p1, self.p2)

    def set_bounding_rect(self, rect: QtCore.QRectF) -> None:
        """Sets the bounding rectangle for the shape."""
        self.set_points(rect.topLeft(), rect.bottomRight())

    def update_bounding_box(self) -> None:
        """Updates the bounding box to match the shape's bounding rectangle."""
        if self.bounding_box is not None:
            self.bounding_box.setRect(self.get_bounding_rect())

    def update_handle_visual_locations(self) -> None:
        """Updates the visual location of each handle."""
        handles_centers = [(handle, handle.rect().center()) for handle in self.handles]
        xs = sorted(center.x() for _, center in handles_centers)
        ys = sorted(center.y() for _, center in handles_centers)
        for handle, center in handles_centers:
            x, y = center.x(), center.y()
            if x == xs[0]:
                # Handle is on the left side
                if y == ys[0]:
                    handle._visual_location = ShapeHandleLocation.TOP_LEFT
                elif y == ys[-1]:
                    handle._visual_location = ShapeHandleLocation.BOTTOM_LEFT
                else:
                    handle._visual_location = ShapeHandleLocation.MIDDLE_LEFT
            elif x == xs[-1]:
                # Handle is on the right side
                if y == ys[0]:
                    handle._visual_location = ShapeHandleLocation.TOP_RIGHT
                elif y == ys[-1]:
                    handle._visual_location = ShapeHandleLocation.BOTTOM_RIGHT
                else:
                    handle._visual_location = ShapeHandleLocation.MIDDLE_RIGHT
            else:
                # Handle is between the left and right sides
                if y == ys[0]:
                    handle._visual_location = ShapeHandleLocation.TOP_MIDDLE
                elif y == ys[-1]:
                    handle._visual_location = ShapeHandleLocation.BOTTOM_MIDDLE
                else:
                    # If the visual location cannot be determined, leave it the same
                    current_visual_location = handle._visual_location.name
                    logging.warning(
                        "Unable to determine visual location of handle at x = %.2f, y = %.2f; "
                        "leaving location as %r",
                        current_visual_location,
                    )

    def update_handle_positions(self) -> None:
        """Updates the position of each handle."""
        for handle in self.handles:
            handle.update_position()

    def get_handle(self, location: ShapeHandleLocation) -> ShapeHandle | None:
        """Returns the shape handle for the given logical location, if one exists."""
        return self._handle_by_logical_location.get(location, None)

    def get_closest_handle(self, pos: QtCore.QPointF) -> tuple[ShapeHandle, float]:
        """Returns the closest grab handle to a point and the corresponding Manhattan distance."""

        def get_handle_distance(pos: QtCore.QPointF, handle: ShapeHandle) -> float:
            return (handle.get_center() - pos).manhattanLength()

        handle_distances = [(handle, get_handle_distance(pos, handle)) for handle in self.handles]
        return min(handle_distances, key=lambda x: x[1])

    def get_nearby_handle(self, pos: QtCore.QPointF) -> ShapeHandle | None:
        """Returns the closest handle that is nearby a point."""
        closest_handle, dist = self.get_closest_handle(pos)
        if dist <= closest_handle._NEARBY_DIST:
            return closest_handle
        else:
            return None


class Rectangle(Shape):
    """A rectangle that is drawable on an interactive display."""

    def _draw_shape(self, p1: QtCore.QPointF, p2: QtCore.QPointF) -> None:
        path = QtGui.QPainterPath()
        path.addRect(QtCore.QRectF(p1, p2))
        self.setPath(path)


class Ellipse(Shape):
    """An ellipse that is drawable on an interactive display."""

    def _draw_shape(self, p1: QtCore.QPointF, p2: QtCore.QPointF) -> None:
        path = QtGui.QPainterPath()
        path.addEllipse(QtCore.QRectF(p1, p2))
        self.setPath(path)


class Line(Shape):
    """A line that is drawable on an interactive display."""

    def _draw_shape(self, p1: QtCore.QPointF, p2: QtCore.QPointF) -> None:
        path = QtGui.QPainterPath()
        path.moveTo(p1)
        path.lineTo(p2)
        self.setPath(path)


def get_image_region(
    image: QtGui.QImage | image_util.ImageArray, shape: Shape
) -> image_util.ImageArray:
    """Returns the region of an image within a shape.

    Raises:
        NotImplementedError if getting the image region is not implemented for the given shape type.
    """
    if isinstance(image, QtGui.QImage):
        image = image_util.qimage_to_ndarray(image)

    # The rectangle must have positive width and height to draw the region
    rect = shape.get_bounding_rect().toRect().normalized()
    x1, y1, x2, y2 = rect.left(), rect.top(), rect.right(), rect.bottom()
    if isinstance(shape, Rectangle):
        return image_util.get_rectangle_region(image, x1, y1, x2, y2)
    elif isinstance(shape, Ellipse):
        return image_util.get_ellipse_region(image, x1, y1, x2, y2)
    elif isinstance(shape, Line):
        return image_util.get_line_region(image, x1, y1, x2, y2)

    raise NotImplementedError(
        f"Getting the image region is not implemented for shape type {type(shape).__name__!r}"
    )


class ShapeHandle(QtWidgets.QGraphicsEllipseItem):
    """A handle for resizing a shape."""

    # Number of pixels within which a point must be to be considered "nearby" a handle
    _NEARBY_DIST = 15

    def __init__(
        self,
        parent_shape: Shape,
        logical_location: ShapeHandleLocation,
        visual_location: ShapeHandleLocation | None = None,
        diameter: float = 3,
    ) -> None:
        super().__init__(parent=parent_shape)
        self._parent_shape = parent_shape
        self._logical_location = logical_location
        self._visual_location = visual_location or logical_location
        self._diameter = diameter

        # Handles should not be visible when first created
        self.hide()

        # Determine the cursor shape to set when the mouse is near the handle
        match visual_location:
            case ShapeHandleLocation.TOP_LEFT | ShapeHandleLocation.BOTTOM_RIGHT:
                self._nearby_cursor_shape = QtCore.Qt.CursorShape.SizeFDiagCursor
            case ShapeHandleLocation.TOP_RIGHT | ShapeHandleLocation.BOTTOM_LEFT:
                self._nearby_cursor_shape = QtCore.Qt.CursorShape.SizeBDiagCursor
            case ShapeHandleLocation.MIDDLE_LEFT | ShapeHandleLocation.MIDDLE_RIGHT:
                self._nearby_cursor_shape = QtCore.Qt.CursorShape.SizeHorCursor
            case ShapeHandleLocation.TOP_MIDDLE | ShapeHandleLocation.BOTTOM_MIDDLE:
                self._nearby_cursor_shape = QtCore.Qt.CursorShape.SizeVerCursor
            case _:
                self._nearby_cursor_shape = QtCore.Qt.CursorShape.OpenHandCursor

        # The handle should have the same color as its associated shape, and should also be
        # cosmetic so that the visual width of its edges do not change with zooming or scaling
        color = parent_shape.pen().color()
        pen = QtGui.QPen(color)
        pen.setWidth(FOCUS_PEN_WIDTH)
        pen.setCosmetic(True)
        self.setPen(pen)
        self.setBrush(color)

        # Update the position of the handle to the corresponding logical location of the shape
        self.update_position()

    @property
    def parent_shape(self) -> Shape:
        return self._parent_shape

    @property
    def logical_location(self) -> ShapeHandleLocation:
        return self._logical_location

    @property
    def visual_location(self) -> ShapeHandleLocation:
        return self._visual_location

    @property
    def diameter(self) -> float:
        return self._diameter

    def get_nearby_cursor_shape(self) -> QtCore.Qt.CursorShape:
        """The cursor shape to set when nearby this handle while the associated shape is active."""
        match self.visual_location:
            case ShapeHandleLocation.TOP_LEFT | ShapeHandleLocation.BOTTOM_RIGHT:
                return QtCore.Qt.CursorShape.SizeFDiagCursor
            case ShapeHandleLocation.TOP_RIGHT | ShapeHandleLocation.BOTTOM_LEFT:
                return QtCore.Qt.CursorShape.SizeBDiagCursor
            case ShapeHandleLocation.MIDDLE_LEFT | ShapeHandleLocation.MIDDLE_RIGHT:
                return QtCore.Qt.CursorShape.SizeHorCursor
            case ShapeHandleLocation.TOP_MIDDLE | ShapeHandleLocation.BOTTOM_MIDDLE:
                return QtCore.Qt.CursorShape.SizeVerCursor
            case _:
                return QtCore.Qt.CursorShape.OpenHandCursor

    def get_center(self) -> QtCore.QPointF:
        """Returns the position of the center of the handle."""
        return self.rect().center()

    def set_center(self, x: float, y: float) -> None:
        """Sets the position of the center of the handle."""
        rect = self.rect()
        rect.moveCenter(QtCore.QPointF(x, y))
        rect.setWidth(self.diameter)
        rect.setHeight(self.diameter)
        self.setRect(rect)

    def update_position(self) -> None:
        """Updates the handle position to match the parent shape."""
        shape_bounding_rect = self.parent_shape.get_bounding_rect()
        left = shape_bounding_rect.left()
        right = shape_bounding_rect.right()
        top = shape_bounding_rect.top()
        bottom = shape_bounding_rect.bottom()
        match self.logical_location:
            case ShapeHandleLocation.TOP_LEFT:
                self.set_center(left, top)
            case ShapeHandleLocation.TOP_MIDDLE:
                self.set_center((left + right) / 2, top)
            case ShapeHandleLocation.TOP_RIGHT:
                self.set_center(right, top)
            case ShapeHandleLocation.MIDDLE_RIGHT:
                self.set_center(right, (top + bottom) / 2)
            case ShapeHandleLocation.BOTTOM_RIGHT:
                self.set_center(right, bottom)
            case ShapeHandleLocation.BOTTOM_MIDDLE:
                self.set_center((left + right) / 2, bottom)
            case ShapeHandleLocation.BOTTOM_LEFT:
                self.set_center(left, bottom)
            case ShapeHandleLocation.MIDDLE_LEFT:
                self.set_center(left, (top + bottom) / 2)
            case _:
                raise TypeError("Unknown shape location")


class ShapeBoundingBox(QtWidgets.QGraphicsRectItem):
    """A bounding box for a shape drawn on an interactive display."""

    def __init__(self, shape: Shape) -> None:
        bounding_rect = shape.get_bounding_rect()
        self._shape = shape
        super().__init__(bounding_rect, shape)

        # Make the item drawn behind its parent instead of on top of it
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemStacksBehindParent)

        # The bounding rect should be the same color as the parent item, but with dotted lines
        parent_color = shape.pen().color()
        dotted_pen = QtGui.QPen(parent_color)
        dotted_pen.setWidthF(SHAPE_PEN_WIDTH)
        dotted_pen.setStyle(QtCore.Qt.PenStyle.DotLine)
        dotted_pen.setCosmetic(True)
        self.setPen(dotted_pen)


@attrs.frozen
class ShapeModification:
    """A modification to a single shape initiated by a mouse click."""

    display: Display
    shape: Shape
    clicked_handle: ShapeHandle | None
    starting_bounding_rect: QtCore.QRectF
    first_click_pos: QtCore.QPointF

    def on_mouse_moved(self, pos: QtCore.QPointF) -> None:
        """Modify the shape when the mouse is moved to the given position."""
        # If no handle was clicked to start the modification, translate the shape
        if self.clicked_handle is None:
            first_click_offset = self.first_click_pos - self.starting_bounding_rect.topLeft()
            move_to = self.shape._constrain_to_image(pos - first_click_offset)
            self.shape.move_to(move_to)
            return

        # Ensure the shape remains within the image bounds after resizing
        constrained_pos = pos
        image_rect = self.shape._parent_image_item.boundingRect()
        constrained_pos.setX(min(image_rect.right(), max(image_rect.left(), constrained_pos.x())))
        constrained_pos.setY(min(image_rect.bottom(), max(image_rect.top(), constrained_pos.y())))
        shape_bounding_rect = self.shape.get_bounding_rect()

        # Resize the shape based on the handle being moved
        match self.clicked_handle.logical_location:
            case ShapeHandleLocation.TOP_LEFT:
                shape_bounding_rect.setTopLeft(constrained_pos)
            case ShapeHandleLocation.TOP_RIGHT:
                shape_bounding_rect.setTopRight(constrained_pos)
            case ShapeHandleLocation.BOTTOM_RIGHT:
                shape_bounding_rect.setBottomRight(constrained_pos)
            case ShapeHandleLocation.BOTTOM_LEFT:
                shape_bounding_rect.setBottomLeft(constrained_pos)
            case ShapeHandleLocation.MIDDLE_LEFT:
                shape_bounding_rect.setLeft(constrained_pos.x())
            case ShapeHandleLocation.TOP_MIDDLE:
                shape_bounding_rect.setTop(constrained_pos.y())
            case ShapeHandleLocation.MIDDLE_RIGHT:
                shape_bounding_rect.setRight(constrained_pos.x())
            case ShapeHandleLocation.BOTTOM_MIDDLE:
                shape_bounding_rect.setBottom(constrained_pos.y())

        # Update the shape, which will also update its handles and bounding box
        self.shape.set_bounding_rect(shape_bounding_rect)

    def on_mouse_released(self) -> None:
        """Finalize the shape modification when the mouse is released."""
        self.shape.update_handle_visual_locations()


class Display(QtWidgets.QGraphicsView):
    """A graphics view for displaying images and interactively drawing shapes over them."""

    # The minimum width and height of a shape, in pixels
    _MIN_SHAPE_SIZE = 4

    def __init__(
        self,
        image_item: QtWidgets.QGraphicsPixmapItem | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        # Create a graphics scene that is always displayed in the top left of the view
        self._scene = QtWidgets.QGraphicsScene()
        self.setScene(self._scene)
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignLeft)

        # Zoom on the mouse rather than the top left of the scene
        self.setTransformationAnchor(QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse)

        # Create the graphics item for displaying images; it should always be the lowermost item
        self._image_item = image_item or QtWidgets.QGraphicsPixmapItem()
        self._scene.addItem(self._image_item)

        # Don't allow shapes to be drawn outside the image
        self._image_item.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemClipsChildrenToShape)

        # Create an off-screen pixel buffer for the image item to speed up rendering
        # NOTE: The cache size defaults to the size of the item's bounding rectangle and should be
        #   updated to match the attached camera's resolution, e.g. 1920x1080.
        self._image_item.setCacheMode(QtWidgets.QGraphicsItem.CacheMode.ItemCoordinateCache)

        # Store shapes drawn on the graphics scene by hex color
        self._shape_by_color: dict[str, Shape | None] = {color: None for color in HEX_COLORS}

        # Define the types of shapes that can be drawn and the order through which they are cycled
        self._shape_types_cycle = itertools.cycle((Rectangle, Ellipse, Line))

        # Set the current shape type (the first one in the cycle, Rectangle)
        self.next_shape_type()

        # Information about the current shape modification (resizing or translating)
        self._current_shape_modification: ShapeModification | None = None

    @QtCore.pyqtSlot(QtGui.QMouseEvent)
    def mouseMoveEvent(self, event: QtGui.QMouseEvent | None) -> None:
        # Use default handling if there is no event data or if no shape is selected
        if event is None or (shape := self.active_shape) is None:
            return super().mouseMoveEvent(event)

        # Map the event coordinates to scene coordinates
        scene_pos = self.mapToScene(event.pos())
        if self._current_shape_modification is None:
            # Active shape is not being resized
            if (nearby_handle := shape.get_nearby_handle(scene_pos)) is not None:
                self.setCursor(nearby_handle.get_nearby_cursor_shape())
            elif shape.contains(scene_pos):
                # Set the cursor to a move indicator when over a shape but not near a handle
                self.setCursor(QtCore.Qt.CursorShape.SizeAllCursor)
            else:
                # Restore the cursor shape to its default when not near a shape
                self.unsetCursor()

            return super().mouseMoveEvent(event)

        # Accept the event since we perform custom handling
        event.accept()

        # Constrain the position to the image so the shape is not resized off the image
        self._current_shape_modification.on_mouse_moved(scene_pos)

        # Ensure that moving the shape does not expand the scene rect
        self.setSceneRect(self.image_item.boundingRect())

    @QtCore.pyqtSlot(QtGui.QMouseEvent)
    def mousePressEvent(self, event: QtGui.QMouseEvent | None) -> None:
        if event is None:
            return super().mousePressEvent(event)

        signature = (event.button(), event.modifiers())
        match signature:
            case (QtCore.Qt.MouseButton.MiddleButton, QtCore.Qt.KeyboardModifier.NoModifier):
                event.accept()
                logging.info("Pressed middle mouse button; resetting interactive display scale")
                self.resetTransform()
            case (QtCore.Qt.MouseButton.RightButton, QtCore.Qt.KeyboardModifier.NoModifier):
                event.accept()
                prev_shape_type = self._current_shape_type.__name__
                self.next_shape_type()
                logging.info(
                    "Cycled shape type from %s to %s",
                    prev_shape_type,
                    self._current_shape_type.__name__,
                )
            case (QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier):
                if (shape := self.active_shape) is None:
                    # No active shape; use default event handling to set focus
                    return super().mousePressEvent(event)

                # A shape is active; accept the event because it will be handled manually
                scene_pos = self.mapToScene(event.pos())
                clicked_handle = shape.get_nearby_handle(scene_pos)
                if clicked_handle is not None or shape.contains(scene_pos):
                    # Clicked a handle or within the shape; prepare for shape modification
                    event.accept()
                    self._current_shape_modification = ShapeModification(
                        display=self,
                        shape=shape,
                        clicked_handle=clicked_handle,
                        starting_bounding_rect=shape.get_bounding_rect(),
                        first_click_pos=scene_pos,
                    )
                else:
                    # Clicked outside the shape; use default event handling to change shape focus
                    super().mousePressEvent(event)
            case (QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.ShiftModifier):
                # Try to add a new shape when shift-left clicking
                event.accept()
                if self.active_shape is not None:
                    self.active_shape.clearFocus()

                scene_pos = self.mapToScene(event.pos())
                p1 = scene_pos
                p2 = p1 + QtCore.QPointF(self._MIN_SHAPE_SIZE, self._MIN_SHAPE_SIZE)
                if (new_shape := self.add_shape(p1, p2)) is not None:
                    # When drawing a new shape, fix the top left corner and move the bottom right
                    self._current_shape_modification = ShapeModification(
                        display=self,
                        shape=new_shape,
                        clicked_handle=new_shape.get_handle(ShapeHandleLocation.BOTTOM_RIGHT),
                        starting_bounding_rect=new_shape.get_bounding_rect(),
                        first_click_pos=self.mapToScene(event.pos()),
                    )
                    new_shape.setFocus()
            case _:
                super().mousePressEvent(event)

    @QtCore.pyqtSlot(QtGui.QMouseEvent)
    def mouseReleaseEvent(self, event: QtGui.QMouseEvent | None) -> None:
        # Finalize shape modification
        if self._current_shape_modification is not None:
            self._current_shape_modification.on_mouse_released()
            self._current_shape_modification = None

        # Always reset the cursor to its default appearance when releasing a mouse button
        self.unsetCursor()

        if event is None or self.active_shape is None:
            # Pass along the event if there is no event data or no shape is selected
            return super().mouseReleaseEvent(event)

        # Indicate that the event has been fully handled
        event.accept()

    @QtCore.pyqtSlot(QtGui.QWheelEvent)
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

                # TODO(ecyoung3): Also scale the handles
        else:
            # Use default event handling if CTRL is not pressed
            super().wheelEvent(event)

    @QtCore.pyqtSlot(QtGui.QKeyEvent)
    def keyPressEvent(self, event: QtGui.QKeyEvent | None) -> None:
        if event is None:
            return

        # Do not use `QKeyEvent.keyCombination()` because it doesn't define `__match_args__`
        match (event.modifiers(), event.key()):
            case (QtCore.Qt.KeyboardModifier.NoModifier, QtCore.Qt.Key.Key_Delete):
                # Pressed the delete key with no modifiers; delete any active shape
                if self.active_shape is not None:
                    self.delete_shape(self.active_shape)

    @property
    def image_item(self) -> QtWidgets.QGraphicsPixmapItem:
        """The item used to display images."""
        return self._image_item

    @property
    def shapes(self) -> list[Shape]:
        """All shapes that have been added to the display."""
        return [shape for _color, shape in self._shape_by_color.items() if shape is not None]

    @property
    def active_shape(self) -> Shape | None:
        """The currently-focused shape."""
        return next((shape for shape in self.shapes if shape.hasFocus()), None)

    def set_image(self, image: QtGui.QImage) -> None:
        """Sets the displayed image."""
        pixmap = QtGui.QPixmap.fromImage(image)
        self.image_item.setPixmap(pixmap)

    def get_next_shape_color(self) -> str | None:
        """Returns the hex value of the next available shape color."""
        return next((color for color, shape in self._shape_by_color.items() if shape is None), None)

    def next_shape_type(self) -> None:
        """Cycles to the next shape type."""
        self._current_shape_type = next(self._shape_types_cycle)

    def add_shape(self, p1: QtCore.QPointF, p2: QtCore.QPointF) -> Shape | None:
        """Adds a new shape of the currently-selected type to the display."""
        # Determine if a new shape can be added
        if (hex_color := self.get_next_shape_color()) is None:
            logging.warning("The maximum number of shapes (%s) already exist", len(HEX_COLORS))
            return None

        # Create the shape based on the currently-selected type
        # NOTE: This will also add it to the scene, since it is created as a child of the image
        #   item, which is already in the scene.
        logging.info("Adding shape with color %r", hex_color)
        shape = self._current_shape_type(p1, p2, QtGui.QColor(hex_color), self.image_item)
        self._shape_by_color[hex_color] = shape
        return shape

    def delete_shape(self, shape: Shape) -> None:
        """Deletes a shape from the display."""
        for color, other_shape in self._shape_by_color.items():
            if shape == other_shape:
                color_to_delete = color
                break
        else:
            logging.warning("Shape not found; unable to delete it from the display")
            return

        # Remove the shape from storage and from the scene, which will also remove the associated
        # bounding box and handles
        logging.info("Deleting shape with color %r", color_to_delete)
        self._shape_by_color[color_to_delete] = None
        if (scene := self.scene()) is not None:
            scene.removeItem(shape)

        # Reset the mouse cursor and any shape modification information
        self.unsetCursor()
        self._current_shape_modification = None
