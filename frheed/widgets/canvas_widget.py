# -*- coding: utf-8 -*-
"""
PyQt widgets for drawing shapes.
"""

from typing import Optional, List, Union

import numpy as np

from PyQt5.QtWidgets import (
    QWidget,
    QLabel,
    QApplication,
    QMenu,
    QAction,
    QMessageBox,
    QActionGroup,
    
    )
from PyQt5.QtGui import (
    QPainter,
    QColor,
    QPen,
    QPixmap,
    
    )
from PyQt5.QtCore import (
    Qt,
    pyqtSignal,
    pyqtSlot,
    QPoint,
    QRect,
    QEvent,
    QSize,
    QLine,
    
    )

from frheed.constants import COLOR_DICT
from frheed.utils import get_qcolor


SHAPE_TYPES = (
    "rectangle",
    "ellipse",
    "line",
    
    )
DEFAULT_COLOR = list(COLOR_DICT.values())[0]
DEFAULT_LINEWIDTH = 1
FOCUSED_LINEWIDTH = 2
EDGE_PAD = 8
MIN_SHAPE_SIZE = 10

_EDGES = ("left", "right", "bottom", "top")
_CORNERS = ("top_left", "top_right", "bottom_left", "bottom_right")
_SHAPE_REGIONS = _EDGES + _CORNERS
_LINE_REGIONS = ("p1", "p2", "middle")
_CURSORS = {
    "left":         Qt.SizeHorCursor,
    "right":        Qt.SizeHorCursor,
    "top":          Qt.SizeVerCursor,
    "bottom":       Qt.SizeVerCursor,
    "top_left":     Qt.SizeFDiagCursor,
    "bottom_right": Qt.SizeFDiagCursor,
    "top_right":    Qt.SizeBDiagCursor,
    "bottom_left":  Qt.SizeBDiagCursor,
    "p1":           Qt.OpenHandCursor,
    "p2":           Qt.OpenHandCursor,
    "middle":       Qt.SizeAllCursor,
    }


# https://stackoverflow.com/a/2233538/10342097
def line_point_dist(line: QLine, point: QPoint) -> float:
    """ Calculate the shortest distance between a QLine and a QPoint """
    
    # Convert coordinates to float
    x1, x2, y1, y2 = map(float, (line.x1(), line.x2(), line.y1(), line.y2()))
    px, py = map(float, (point.x(), point.y()))
    dx, dy = map(float, (line.dx(), line.dy()))  # should these be abs() values?

    # Calculate norm
    norm = dx**2 + dy**2
    
    # If norm == 0, return 0
    if norm == 0:
        return 0.
    
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


class CanvasWidget(QLabel):
    """ A widget for drawing shapes """
    shape_deleted = pyqtSignal(object)
    
    def __init__(self, parent: QWidget = None, shape_limit: int = 10):
        super().__init__(parent)
        self._shape_limit = shape_limit
        
        # Enable mouse tracking so it can detect mouseEvent
        self.setMouseTracking(True)
        
        # Enable context menus
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        
        # Create context menu
        self.menu = QMenu(self)
        self.clear_canvas_action = QAction("&Clear shapes", self)
        self.menu.addAction(self.clear_canvas_action)
        self.menu.addSeparator()
        
        # Create submenu for selecting shape
        self.shape_type_menu = self.menu.addMenu("&Select shape type")
        self.shape_action_group = QActionGroup(self.menu)
        for shape_type in SHAPE_TYPES:
            action = QAction(f"&{shape_type.title()}", self)
            action.setCheckable(True)
            action.setChecked(shape_type == SHAPE_TYPES[0])
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
        self._draw_start_pos: Optional[QPoint] = None
        
        self._resizing: bool = False
        self._resizing_from: Optional[str] = None
        
        self._moving: bool = False
        self._move_start_pos: Optional[QPoint] = None
        
        self._shapes: List[CanvasShape] = []
        self._active_shape: Optional[CanvasShape] = None
        
        self._pressed_buttons: List[int] = []
        
        # Connect signals
        self.customContextMenuRequested.connect(self.menu_requested)
        self.clear_canvas_action.triggered.connect(self.clear_canvas)
        
    def resizeEvent(self, event: QEvent) -> None:
        super().resizeEvent(event)
        
        # Resize the shapes
        old, new = event.oldSize(), self.size()
        [shape.rescale(old, new) for shape in self.shapes]
        
    def keyPressEvent(self, event: QEvent) -> None:
        super().keyPressEvent(event)
        
        # Delete active shape when "Delete" key is pressed
        if event.key() == Qt.Key_Delete:
            if self.active_shape is not None:
                self.active_shape.delete()
                
                # Restore the mouse cursor
                self.app.restoreOverrideCursor()
        
    def mousePressEvent(self, event: QEvent) -> None:
        super().mousePressEvent(event)

        # Left button events
        if event.button() == Qt.LeftButton:
            
            # Drawing should not start if another shape is active
            if self.active_shape is None:
                self._draw_start_pos = event.pos()
                
            # Indicate that resizing has started if a shape is active
            else:
                if self.active_shape.nearest_region(event.pos()) == "middle":
                    self.moving = True
                    self._move_start_pos = self.active_shape.p1() - event.pos()
                else:
                    self.resizing = True
                    self._resizing_from = self.active_shape.nearest_region(event.pos())
            
        # Right button events
        elif event.button() == Qt.RightButton:
            # self.app.setOverrideCursor(Qt.ArrowCursor)
            self.app.restoreOverrideCursor()
        
        # Middle button events
        elif event.button() == Qt.MiddleButton:
            
            # Indicate that shape movement can start
            if self.active_shape is not None:
                self.moving = True
                if isinstance(self.active_shape, CanvasShape):
                    self._move_start_pos = self.active_shape.topLeft() - event.pos()
                elif isinstance(self.active_shape, CanvasLine):
                    self._move_start_pos = self.active_shape.p1() - event.pos()
        
    def mouseReleaseEvent(self, event: QEvent) -> None:
        # Left button events
        if event.button() == Qt.LeftButton:
            self._draw_start_pos = None
            self.drawing = False
            self.resizing = False
            
            # If moving a line, stop
            if self.moving and not self.drawing:
                self.moving = False
                self._move_start_pos = None
            
        # Right button events
        elif event.button() == Qt.RightButton:
            
            # Restore cursor if not drawing, moving, or resizing
            if not (self.drawing or self.moving or self.resizing):
                self.app.setOverrideCursor(Qt.ArrowCursor)
                # self.app.restoreOverrideCursor()
                return
            
        # Middle button events
        elif event.button() == Qt.MiddleButton:
            self.moving = False
            self._move_start_pos = None
            
        # Normalize all shapes
        [shape.normalize() for shape in self.shapes]
        self.draw()
        
        # Re-check the override cursor if released mouse is not right mouse
        if self.active_shape is not None and event.button() != Qt.RightButton:
            region = self.active_shape.nearest_region(event.pos())
            if region in _CURSORS:
                self.app.setOverrideCursor(_CURSORS[region])
        else:
            self.app.restoreOverrideCursor()
        
    def mouseMoveEvent(self, event: QEvent) -> None:
        super().mouseMoveEvent(event)
        
        # Get the event position
        pos = event.pos()

        # Start drawing if mouse has moved > 10 pixels while LMB pressed
        if self.can_draw:
            x1, y1 = self._draw_start_pos.x(), self._draw_start_pos.y()
            x2, y2 = pos.x(), pos.y()
            sep = np.sqrt((x2-x1)**2 + (y2-y1)**2)
            if sep > MIN_SHAPE_SIZE:
                self.drawing = True
                self.add_shape(self._draw_start_pos)
        
        # Expand the active shape if one is being drawn
        if self.active_shape is not None and self.drawing:
            if self.active_shape.kind in ["rectangle", "ellipse"]:
                self.active_shape.resize("bottom_right", pos)
            elif self.active_shape.kind == "line":
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
                    if region in _CURSORS:
                        self.app.setOverrideCursor(_CURSORS[region])
                    
                # Deactivate shapes not near the cursor
                else:
                    shape.deactivate()
                    
        # If the LMB is pressed and the cursor is an open hand,
        # make the cursor a closed hand
        if (self.app.overrideCursor() is not None 
                and self.button_pressed(Qt.LeftButton)):
            if self.app.overrideCursor().shape() == Qt.OpenHandCursor:
                self.app.setOverrideCursor(Qt.ClosedHandCursor)
                    
        # Restore the mouse cursor if no shapes active
        self.app.restoreOverrideCursor() if self.active_shape is None else None
                    
    @property
    def app(self) -> QApplication:
        return QApplication.instance()
            
    @property
    def shape_type(self) -> str:
        return self.shape_action_group.checkedAction().text().strip("&")
    
    @property
    def shape_limit(self) -> int:
        return self._shape_limit
    
    @shape_limit.setter
    def shape_limit(self, limit: int) -> None:
        self._shape_limit = limit
        if len(self.shapes) > self._shape_limit:
            self._shapes = self._shapes[:self._shape_limit]
            self.draw()
            
    @property
    def can_draw(self) -> bool:
        return (self._draw_start_pos is not None 
                and self.button_pressed(Qt.LeftButton)
                and not self.drawing 
                and self.active_shape is None
                and not self.resizing)
    
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
    def resizing_from(self) -> Union[str, None]:
        return self._resizing_from
        
    @property
    def moving(self) -> bool:
        return self._moving
    
    @moving.setter
    def moving(self, moving: bool) -> None:
        self._moving = moving
        
        # Update the mouse cursor
        if moving:
            self.app.setOverrideCursor(Qt.SizeAllCursor)
        else:
            self.app.restoreOverrideCursor()
    
    @property
    def shapes(self) -> List["CanvasShape"]:
        return self._shapes

    @shapes.setter
    def shapes(self, shapes: List) -> None:
        self._shapes = shapes
        self.active_shape = None
        self.draw()

    @property
    def active_shape(self) -> "CanvasShape":
        return self._active_shape
    
    @active_shape.setter
    def active_shape(self, shape: "CanvasShape") -> None:
        self._active_shape = shape
        
        # Deactivate other shapes so only one can be active at once
        for other_shape in self.shapes:
            if id(shape) == id(other_shape):
                continue
            other_shape.deactivate()
            
        # Restore mouse cursor if no active shapes
        if self._active_shape is None:
            self.app.restoreOverrideCursor()
            
    @pyqtSlot(QPoint)
    def menu_requested(self, p: QPoint) -> None:
        """ Show the right-click popup menu """
        # Ignore right click while drawing, moving or resizing
        if self.drawing or self.moving or self.resizing:
            return
        
        # Show the menu
        self.menu.popup(self.mapToGlobal(p))
        
    def button_pressed(self, button: int) -> bool:
        return bool(button & int(QApplication.mouseButtons()))
    
    def add_shape(self, pos: QPoint) -> None:
        """ Create a CanvasRect and add it to the canvas """
        
        # Make sure the shape limit has not been hit
        if len(self.shapes) >= self.shape_limit:
            self.drawing = False
            msg = f"Maximum of {self.shape_limit} shapes allowed."
            return QMessageBox.information(self, "Notice", msg)
        
        # Define initial shape dimensions
        x, y, w, h = pos.x(), pos.y(), 0, 0
        
        # Create the shape or line
        if self.shape_type.lower() in ["rectangle", "ellipse"]:
            shape = CanvasShape(x, y, w, h)
            shape.kind = self.shape_type.lower()
            
        elif self.shape_type.lower() == "line":
            shape = CanvasLine(x, y, x, y)
        
        # Get the next color
        color_idx = len(self.shapes) % (len(COLOR_DICT) + 1)
        shape.color = list(COLOR_DICT.values())[color_idx]
        
        # Assign the canvas to the shape
        shape.canvas = self
        
        # Activate the shape, which will also draw it
        shape.activate()
        
    def draw(self) -> None:
        """ Redraw all the shapes """
        
        # Get a fresh pixmap
        pixmap = QPixmap(self.size())
        pixmap.fill(QColor("transparent"))
        
        # Get a fresh painter
        painter = QPainter(pixmap)
        # painter.setRenderHint(QPainter.Antialiasing)
        
        # Set the pen
        pen = QPen()
        pen.setCosmetic(True)
        painter.setPen(pen)
        
        # Draw each of the shapes
        for shape in self.shapes:
            
            # Set pen properties
            pen.setColor(shape.color)
            pen.setWidth(shape.linewidth)
            painter.setPen(pen)
            
            # Draw the shape
            if shape.kind == "rectangle":
                painter.drawRect(shape)
            elif shape.kind == "ellipse":
                painter.drawEllipse(shape)
            elif shape.kind == "line":
                painter.drawLine(shape)
                
        # !!!IMPORTANT!!! End the painter otherwise the GUI will crash
        painter.end()  
        
        # Update the pixmap
        self.setPixmap(pixmap)
        
    @pyqtSlot()
    def clear_canvas(self) -> None:
        """ Clear all shapes and reset the canvas """
        # Use the delete function so signals are properly emitted
        # Can't use list comprehension because size of list will change during iteration
        while self.shapes:
            self.shapes[0].delete()

        
class CanvasShape(QRect):
    """ A custom QRect that can be assigned to a CanvasWidget. """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Attributes to be assigned later
        self._kind = SHAPE_TYPES[0]
        self._linewidth: int = DEFAULT_LINEWIDTH
        self._color: str = DEFAULT_COLOR
        self._color_name: Optional[str] = None
        self._canvas: Optional[CanvasWidget] = None
        
        # Store floating point coords for resizing precision
        self.float_coords = super().getCoords()
        
    def moveTo(self, p: QPoint) -> None:
        """ Move the top left corner to point 'p' """
        
        # Make sure the resulting position is valid
        if self.canvas is not None:
            new_shape = QRect(p.x(), p.y(), self.width(), self.height())
            x1, y1, x2, y2 = new_shape.getCoords()
            width, height = self.canvas.width(), self.canvas.height()
            lw = self.linewidth
            if x1 < 0 or y1 < 0 or x2 > (width - lw) or y2 > (height - lw):
                return
        
        # Move the shape
        super().moveTo(p)
        self.update()
        
        # Update float coords
        self.float_coords = self.getCoords()
        
    def normalize(self) -> None:
        """ Normalize the shape so it has non-negative width/height """
        
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
            
        # Update float coords
        self.float_coords = self.getCoords()
            
    @property
    def kind(self) -> str:
        return self._kind
    
    @kind.setter
    def kind(self, kind: str) -> None:
        self._kind = kind
        self.update()
        
    @property
    def color(self) -> Union[QColor, None]:
        return self._color
    
    @color.setter
    def color(self, color: Union[str, tuple, QColor]) -> None:
        self._color = get_qcolor(color)
        
    @property
    def color_name(self) -> str:
        return self.color.name()
    
    @property
    def canvas(self) -> Union[CanvasWidget, None]:
        return self._canvas
    
    @canvas.setter
    def canvas(self, canvas: CanvasWidget) -> None:
        if not isinstance(canvas, CanvasWidget):
            raise TypeError(f"Got {type(canvas)}, expected CanvasWidget")
        self._canvas = canvas
        self.update()
        
        # Store the shape in the canvas's list of shapes
        if id(self) not in map(id, self._canvas.shapes):
            self._canvas._shapes.append(self)
        
    @property
    def linewidth(self) -> int:
        return self._linewidth
        
    @linewidth.setter
    def linewidth(self, linewidth: int) -> None:
        self._linewidth = linewidth
        self.update()
        
    @property
    def active(self) -> bool:
        return id(self) == id(getattr(self.canvas, "active_shape", self))
        
    @property
    def top_left_region(self) -> tuple:
        """ Top left corner bounding box (xmin, ymin, xmax, ymax) """
        x1, y1, x2, y2 = self.getCoords()
        return ((x1 - EDGE_PAD), (y1 - EDGE_PAD), (x1 + EDGE_PAD), (y1 + EDGE_PAD))
    
    def near_top_left(self, p: QPoint) -> bool:
        xmin, ymin, xmax, ymax = self.top_left_region
        return (xmin < p.x() < xmax) and (ymin < p.y() < ymax) 
    
    def dist_from_top_left(self, p: QPoint) -> float:
        """ Get the distance from a point to the top left corner """
        return np.sqrt((self.top() - p.y())**2 + (self.left() - p.x())**2)
        
    @property
    def top_right_region(self) -> tuple:
        """ Top right corner bounding box (xmin, ymin, xmax, ymax) """
        x1, y1, x2, y2 = self.getCoords()
        return ((x2 - EDGE_PAD), (y1 - EDGE_PAD), (x2 + EDGE_PAD), (y1 + EDGE_PAD))
    
    def near_top_right(self, p: QPoint) -> bool:
        xmin, ymin, xmax, ymax = self.top_right_region
        return (xmin < p.x() < xmax) and (ymin < p.y() < ymax) 
    
    def dist_from_top_right(self, p: QPoint) -> float:
        """ Get the distance from a point to the top right corner """
        return np.sqrt((self.top() - p.y())**2 + (self.right() - p.x())**2)
        
    @property
    def bottom_left_region(self) -> tuple:
        """ Bottom left corner bounding box (xmin, ymin, xmax, ymax) """
        x1, y1, x2, y2 = self.getCoords()
        return ((x1 - EDGE_PAD), (y2 - EDGE_PAD), (x1 + EDGE_PAD), (y2 + EDGE_PAD))
    
    def near_bottom_left(self, p: QPoint) -> bool:
        xmin, ymin, xmax, ymax = self.bottom_left_region
        return (xmin < p.x() < xmax) and (ymin < p.y() < ymax)
    
    def dist_from_bottom_left(self, p: QPoint) -> float:
        """ Get the distance from a point to the bottom left corner """
        return np.sqrt((self.bottom() - p.y())**2 + (self.left() - p.x())**2)
        
    @property
    def bottom_right_region(self) -> tuple:
        """ Bottom right corner bounding box (xmin, ymin, xmax, ymax) """
        x1, y1, x2, y2 = self.getCoords()
        return ((x2 - EDGE_PAD), (y2 - EDGE_PAD), (x2 + EDGE_PAD), (y2 + EDGE_PAD))
    
    def near_bottom_right(self, point: QPoint) -> bool:
        xmin, ymin, xmax, ymax = self.bottom_right_region
        return (xmin < point.x() < xmax) and (ymin < point.y() < ymax)
    
    def dist_from_bottom_right(self, p: QPoint) -> float:
        """ Get the distance from a point to the bottom left corner """
        return np.sqrt((self.bottom() - p.y())**2 + (self.right() - p.x())**2)
        
    @property
    def left_region(self) -> tuple:
        """ Left region bounding box (xmin, ymin, xmax, ymax) """
        x1, y1, x2, y2 = self.getCoords()
        return ((x1 - EDGE_PAD), (y1 + EDGE_PAD), (x1 + EDGE_PAD), (y2 - EDGE_PAD))
    
    def near_left(self, p: QPoint) -> bool:
        xmin, ymin, xmax, ymax = self.left_region
        return (xmin < p.x() < xmax) and (ymin < p.y() < ymax)
    
    def dist_from_left(self, p: QPoint) -> float:
        """ Get the distance from a point to the left edge """
        return abs(p.x() - self.left())
    
    @property
    def right_region(self) -> tuple:
        """ Right region bounding box (xmin, ymin, xmax, ymax) """
        x1, y1, x2, y2 = self.getCoords()
        xmin, xmax = (x2 - EDGE_PAD), (x2 + EDGE_PAD)
        ymin, ymax = (y1 + EDGE_PAD), (y2 - EDGE_PAD)
        return (xmin, ymin, xmax, ymax)
    
    def near_right(self, p: QPoint) -> bool:
        xmin, ymin, xmax, ymax = self.right_region
        return (xmin < p.x() < xmax) and (ymin < p.y() < ymax)
    
    def dist_from_right(self, point: QPoint) -> float:
        """ Get the distance from a point to the right edge """
        return abs(point.x() - self.right())
    
    @property
    def bottom_region(self) -> tuple:
        """ Bottom region bounding box (xmin, ymin, xmax, ymax) """
        x1, y1, x2, y2 = self.getCoords()
        xmin, xmax = (x1 + EDGE_PAD), (x2 - EDGE_PAD)
        ymin, ymax = (y2 - EDGE_PAD), (y2 + EDGE_PAD)
        return (xmin, ymin, xmax, ymax)
    
    def near_bottom(self, p: QPoint) -> bool:
        xmin, ymin, xmax, ymax = self.bottom_region
        return (xmin < p.x() < xmax) and (ymin < p.y() < ymax)
    
    def dist_from_bottom(self, p: QPoint) -> float:
        """ Get the distance from a point to the bottom edge """
        return abs(p.y() - self.bottom())
        
    @property
    def top_region(self) -> tuple:
        """ Top region bounding box (xmin, ymin, xmax, ymax) """
        x1, y1, x2, y2 = self.getCoords()
        xmin, xmax = (x1 + EDGE_PAD), (x2 - EDGE_PAD)
        ymin, ymax = (y1 - EDGE_PAD), (y1 + EDGE_PAD)
        return (xmin, ymin, xmax, ymax)
    
    def near_top(self, p: QPoint) -> bool:
        xmin, ymin, xmax, ymax = self.top_region
        return (xmin < p.x() < xmax) and (ymin < p.y() < ymax)
    
    def dist_from_top(self, p: QPoint) -> float:
        """ Get the distance from a point to the top edge """
        return abs(p.y() - self.top())
    
    def point_nearby(self, p: QPoint) -> bool:
        """ Check if a QPoint is near any border of the shape """
        return any(getattr(self, f"near_{reg}")(p) for reg in _SHAPE_REGIONS)
    
    def nearby_regions(self, p: QPoint) -> List[str]:
        """ Get list of regions that are near a point """
        return [r for r in _SHAPE_REGIONS if getattr(self, f"near_{r}")(p)]
    
    def nearest_region(self, p: QPoint) -> Union[str, None]:
        """ Determine which region of the shape is closest to the point """
        
        # Get list of nearby regions
        regions = self.nearby_regions(p)
        if not regions:
            return None
        
        # Return region if only one is nearby
        elif len(regions) == 1:
            return regions[0]
        
        # Need to determine which region is closest if there are multiple
        else:
            # Get distances from the point to each region
            seps = [(r, getattr(self, f"dist_from_{r}")(p)) for r in regions]
            
            # Get the name of the nearest region
            return sorted(seps, key=lambda i: i[1])[0][0]
    
    @property
    def mask(self) -> np.ndarray:
        """ 
        Get a numpy mask where pixels inside the shape = True.
        https://stackoverflow.com/a/44874588/10342097
        """
        
        # Get dimensions of canvas if it exists, otherwise the shape dimensions
        if self.canvas is None:
            width, height = self.width(), self.height()
        else:
            size = self.canvas.size()
            width, height = size.width(), size.height()
            
        # Get the center of the shape
        center: QPoint = self.center()
        h, k = center.x(), center.y()
        
        # Get the shape dimensions
        x1, y1, x2, y2 = self.getCoords()
        a = max(abs(x2 - x1) / 2, 1)  # avoid divide by 0
        b = max(abs(y2 - y1) / 2, 1)  # avoid divide by 0
        
        # Create the mask by calculating which pixels fall inside the shape
        # For a rectangle, this is simple
        if self.kind == "rectangle":
            mask = np.full((height, width), False, dtype=bool)
            mask[y1:y2+1, x1:x2+1] = True
            
        # Equation for ellipse: ((x - h)^2 / a^2) + ((y - k)^2 / b^2) = 1
        # with center (h, k) and horizontal/vertical radii (a, b)
        else:
            Y, X = np.ogrid[:height, :width]
            mask = ((((X - h)**2 / (a**2)) + ((Y - k)**2 / (b**2))) <= 1)
            
        return mask
            
    def rescale(self, old: QSize, new: QSize) -> None:
        """ Scale the shape when the canvas changes """
        
        # Get the scale factors
        w0, h0 = old.width(), old.height()
        w1, h1 = new.width(), new.height()
        w_scale, h_scale = (w1 / max(w0, 1)), (h1 / max(h0, 1))
        
        # Work in floating point to avoid rounding problems
        x1, y1, x2, y2 = self.float_coords
        x1_new, x2_new = (x1 * w_scale), (x2 * w_scale)
        y1_new, y2_new = (y1 * h_scale), (y2 * h_scale)
        self.float_coords = x1_new, y1_new, x2_new, y2_new
            
        # Rescale the shape
        self.setCoords(int(x1_new), int(y1_new), int(x2_new), int(y2_new))
        self.update()
        
    def resize(self, region: str, p: QPoint) -> None:
        """ Resize the shape using the mouse """
        
        # Make sure the position is valid
        p = self.validate_position(p)
        
        if region == "left":
            self.setLeft(p.x())
        
        elif region == "right":
            self.setRight(p.x())
        
        elif region == "top":
            self.setTop(p.y())
        
        elif region == "bottom":
            self.setBottom(p.y())
        
        elif region == "top_left":
            self.setTopLeft(p)
        
        elif region == "top_right":
            self.setTopRight(p)
        
        elif region == "bottom_left":
            self.setBottomLeft(p)
        
        elif region == "bottom_right":
            self.setBottomRight(p)
            
        # Update the canvas
        self.update()
        
        # Update the float coords
        self.float_coords = self.getCoords()
        
    def validate_position(self, p: QPoint) -> QPoint:
        """ Make sure a QPoint falls inside the canvas """
        if self.canvas is None:
            return p
        x = max(0, min(self.canvas.width() - self.linewidth, p.x()))
        y = max(0, min(self.canvas.height() - self.linewidth, p.y()))
        return QPoint(x, y)
        
    def update(self) -> None:
        """ Redraw this shape (and all others) on the parent canvas """
        if self.canvas is not None:
            self.canvas.draw()
            
    def delete(self) -> None:
        """ Remove the shape from the associated canvas """
        if self.canvas is not None:
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
        if self.active and self.canvas is not None:
            self.canvas.active_shape = None
        self.linewidth = DEFAULT_LINEWIDTH
        self.update()


class CanvasLine(QLine):
    """ A custom QLine that can be assigned to a CanvasWidget. """
    
    # Inherit methods from CanvasShape
    validate_position = CanvasShape.validate_position
    update = CanvasShape.update
    delete = CanvasShape.delete
    activate = CanvasShape.activate
    deactivate = CanvasShape.deactivate
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Attributes to be assigned later
        self._linewidth: int = DEFAULT_LINEWIDTH
        self._color: str = DEFAULT_COLOR
        self._color_name: Optional[str] = None
        self._canvas: Optional[CanvasWidget] = None
        
        # Store floating point coords for resizing precision
        self.float_coords = self.getCoords()
        
    def getCoords(self) -> tuple:
        """ Convenience function since QLine doesn't implement it """
        # NOTE: don't sort because it will cause line to redraw incorrectly
        # x1, x2 = sorted([self.x1(), self.x2()])
        # y1, y2 = sorted([self.y1(), self.y2()])
        # return (x1, y1, x2, y2)
        return (self.x1(), self.y1(), self.x2(), self.y2())
        
    def setCoords(self, x1: int, y1: int, x2: int, y2: int) -> None:
        self.setLine(x1, y1, x2, y2)
        
    def moveTo(self, p: QPoint) -> None:
        """ Move the line's p1 to a new point """
        
        # Get new coordinates
        new_p2 = QPoint(p.x() + self.dx(), p.y() + self.dy())
        
        # Validate coordinates
        if self.canvas is not None:
            new_line = CanvasLine(p, new_p2)
            x1, y1, x2, y2 = new_line.getCoords()
            xmin, xmax = sorted([x1, x2])
            ymin, ymax = sorted([y1, y2])
            width, height = self.canvas.width(), self.canvas.height()
            lw = self.linewidth
            if xmin < 0 or ymin < 0 or xmax > (width - lw) or ymax > (height - lw):
                return
        
        # Move the line and update the canvas
        self.setPoints(p, new_p2)
        self.update()
        
        # Update float coords
        self.float_coords = self.getCoords()
        
    def normalize(self) -> None:
        """ This doesn't do anything but is provided since CanvasShape has it """
        
    def width(self) -> int:
        """ Make sure width is always positive """
        return abs(super().dx())
    
    def height(self) -> int:
        """ Make sure height is always positive """
        return abs(super().dy())
    
    @property
    def kind(self) -> str:
        return "line"
    
    @property
    def canvas(self) -> CanvasWidget:
        return self._canvas
    
    @canvas.setter
    def canvas(self, canvas: CanvasWidget) -> None:
        self._canvas = canvas
        self._canvas._shapes.append(self)
        
    @property
    def color(self) -> Union[QColor, None]:
        return self._color
    
    @color.setter
    def color(self, color: Union[str, tuple, QColor]) -> None:
        self._color = get_qcolor(color)
        
    @property
    def color_name(self) -> str:
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
        return id(self) == id(getattr(self.canvas, "active_shape", self))
    
    def dist_from_line(self, p: QPoint) -> float:
        return line_point_dist(self, p)
    
    def point_nearby(self, p: QPoint) -> float:
        """ Determine if a point is near the line """
        return self.dist_from_line(p) < EDGE_PAD
        
    def dist_from_p1(self, p: QPoint) -> float:
        """ Get the distance from a point to p1 of the line """
        return np.sqrt((p.x() - self.x1())**2 + (p.y() - self.y1())**2)
    
    def near_p1(self, p: QPoint) -> bool:
        """ Determine if a point is near p1 of the line """
        return self.dist_from_p1(p) < EDGE_PAD
        
    def dist_from_p2(self, p: QPoint) -> float:
        """ Get the distance from a point to p2 of the line """
        return np.sqrt((p.x() - self.x2())**2 + (p.y() - self.y2())**2)
        
    def near_p2(self, p: QPoint) -> bool:
        """ Determine if a point is near p2 of the line """
        return self.dist_from_p2(p) < EDGE_PAD
    
    def dist_from_middle(self, p: QPoint) -> float:
        return self.dist_from_line(p)
    
    def near_middle(self, p: QPoint) -> bool:
        """ Determine if a point is near the line (excluding the ends) """
        return self.point_nearby(p) and not (self.near_p1(p) or self.near_p2(p))
    
    def nearby_regions(self, p: QPoint) -> list:
        """ Get a list of regions that are near a point """
        return [r for r in _LINE_REGIONS if getattr(self, f"near_{r}")(p)]
    
    def nearest_region(self, p: QPoint) -> Union[str, None]:
        """ Determine which region of the line is closest to the point """
        
        # Get list of nearby regions
        regions = self.nearby_regions(p)
        if not regions:
            return None
        
        # Return region if only one is nearby
        elif len(regions) == 1:
            return regions[0]
        
        # Need to determine which region is closest if there are multiple
        else:
            # Get distances from the point to each region
            seps = [(r, getattr(self, f"dist_from_{r}")(p)) for r in regions]
            
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
        num = max(self.width(), self.height()) * 10  # this can probably be optimized
        x = np.linspace(min(x1, width - 1), min(x2, width - 1), num, endpoint=False)
        y = np.linspace(min(y1, height - 1), min(y2, height - 1), num, endpoint=False)
        
        # Mask values along the line
        mask[y.astype(np.int), x.astype(np.int)] = True
        return mask
        
    def rescale(self, old: QSize, new: QSize) -> None:
        """ Scale the line when the canvas changes """
        
        # Get the scale factors
        w0, h0 = old.width(), old.height()
        w1, h1 = new.width(), new.height()
        w_scale, h_scale = (w1 / max(w0, 1)), (h1 / max(h0, 1))
        
        # Work in floating point to avoid rounding problems
        x1, y1, x2, y2 = self.float_coords
        x1_new, x2_new = (x1 * w_scale), (x2 * w_scale)
        y1_new, y2_new = (y1 * h_scale), (y2 * h_scale)
        self.float_coords = x1_new, y1_new, x2_new, y2_new
            
        # Rescale the shape
        self.setCoords(int(x1_new), int(y1_new), int(x2_new), int(y2_new))
        self.update()
        
    def resize(self, region: str, p: QPoint) -> None:
        """ Resize the line using the mouse """
        
        # Make sure the position is valid
        p = self.validate_position(p)
        
        if region == "p1":
            self.setP1(p)
        
        elif region == "p2":
            self.setP2(p)
        
        # Update the canvas
        self.update()
        
        # Update the float coords
        self.float_coords = self.getCoords()
        

if __name__ == "__main__":
    def test():
        import sys
        from PyQt5.QtWidgets import QApplication
        from frheed.utils import test_widget
        
        app = QApplication.instance() or QApplication([])
        
        widget, app = test_widget(CanvasWidget, block=False, parent=None)
        
        sys.exit(app.exec_())
    
    test()
