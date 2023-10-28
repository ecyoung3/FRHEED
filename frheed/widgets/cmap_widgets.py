# -*- coding: utf-8 -*-
"""
Widgets for displaying colormaps.
"""

from PyQt5.QtWidgets import (
    QWidget,
    QGridLayout,
    QAction, 
    QMenu, 
    QProxyStyle,
    QStyle,
    QActionGroup,
    
    )
from PyQt5.QtGui import (
    QIcon,
    
    )
from PyQt5.QtCore import pyqtSignal, pyqtSlot

import numpy as np

from frheed.image_processing import (
    get_valid_colormaps, 
    apply_cmap,
    ndarray_to_qpixmap,
    
    )
from frheed.utils import get_logger
from frheed.settings import DEFAULT_CMAP


# Local settings
CMAP_W = 256
CMAP_H = 256
MENU_TEXT = "Select color&map"

# Logger
logger = get_logger("frheed")

# Todo list
TODO = """
Make clicking one of the actions actually change the colormap

""".strip("\n").split("\n")


class ColormapSelection(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._parent = parent
        
        # Create layout
        self.layout = QGridLayout()
        self.layout.setContentsMargins(4, 4, 4, 4)
        self.layout.setSpacing(4)
        self.setLayout(self.layout)
        
        # 


class ColormapMenu(QMenu):
    cmap_selected = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Set menu text
        self.setTitle(MENU_TEXT)
        
        # Create exclusive action group
        # TODO: Figure out how to implement this
        # group = QActionGroup(self)
        
        # Add all colormap menu actions
        cmaps = get_valid_colormaps()
        [self.addAction(ColormapAction(c, self)) for c in cmaps]
        
        # Update style to resize icon
        # TODO: Figure out how to indicate item is checked w/ custom style
        # self.setStyle(ColormapProxyStyle())
        
        # Make the menu scrollable
        self.setStyleSheet(self.styleSheet() +
                           """
                           QMenu {
                               menu-scrollable: 1;
                           }
                           """)
        
        # Set default colormap
        self.select_cmap(DEFAULT_CMAP)
        
        # Connect signals
        self.cmap_selected.connect(self.select_cmap)
        
    @property
    def cmap(self) -> str:
        """ Return the hovered colormap (if any) or the checkd colormap. """
        return self.hovered_cmap or self.selected_cmap
        
    @property
    def hovered_cmap(self) -> str:
        if self.activeAction() is not None:
            return self.activeAction().text()
        else:
            return None
        
    @property
    def selected_cmap(self) -> str:
        action = next((a for a in self.checked_actions), None)
        if action is not None:
            return action.text()
        else:
            raise TypeError
        
    @property
    def checked_actions(self) -> list:
        return [a for a in self.actions() if a.isChecked()]
        
    def get_action(self, cmap: str) -> QAction:
        return next((a for a in self.actions() if a.text() == cmap), None)
    
    @pyqtSlot(str)
    def select_cmap(self, cmap: str) -> None:
        action = self.get_action(cmap)
        if action is not None:
            # Uncheck any selected colormaps (should only be one)
            [a.setChecked(False) for a in self.checked_actions]
            
            # Check the colormap
            action.setChecked(True)
            
        else:
            raise AttributeError(f"No action found for {cmap}")


class ColormapAction(QAction):
    def __init__(self, colormap: str, parent=None):
        super().__init__(colormap, parent)
        self._parent = parent
        self.setCheckable(True)
        self.set_colormap(colormap)
        
    @property
    def colormap(self) -> str:
        return self.text()
        
    @colormap.setter
    def colormap(self, colormap: str) -> None:
        self.set_colormap(colormap)
    
    def set_colormap(self, colormap: str) -> None:
        """ Set the current colormap. """
        # Make sure colormap is valid
        if colormap not in get_valid_colormaps():
            ex = ValueError(f"Colormap {colormap} not found")
            logger.exception(ex)
            raise ex
        
        # Set text
        self.setText(colormap)
        
        # Get colormap icon
        # TODO : Finish + test
        icon = ColormapIcon(colormap)
        self.setIcon(icon)
        
        # Connect signal
        if hasattr(self._parent, "cmap_selected"):
            # Disconnect any existing signals
            try:
                self.triggered.disconnect()
            except TypeError:
                pass
            
            # Connect new signals
            self.triggered.connect(
                lambda: self._parent.cmap_selected.emit(colormap)
                )
        

class ColormapIcon(QIcon):
    def __init__(self, colormap: str):
        self.cmap_array = get_cmap_array(colormap, CMAP_H)
        pixmap = ndarray_to_qpixmap(self.cmap_array)
        super().__init__(pixmap)


class ColormapProxyStyle(QProxyStyle):
    """ Make the QAction icon larger. """
    def pixelMetric(self, metric, option=None, widget=None):
        if metric == QStyle.PM_SmallIconSize:
            return 30
        else:
            return QProxyStyle.pixelMetric(self, metric, option, widget)


def get_cmap_array(cmap: str, h: int) -> np.ndarray:
    """ Get a colormap sample with a particular size. """
    # Create array
    arr = np.ones((h, CMAP_W))
    
    # Set values of array
    for i in range(0, CMAP_W):
        arr[:, i] = i
    
    # Apply colormap
    cmapped = apply_cmap(arr, cmap)
    return cmapped


if __name__ == "__main__":
    class tests:
        def __init__(self):
            funcs = [a for a in dir(self) if a.startswith("test_")]
            for func in funcs:
                getattr(self, func)()
                
        @staticmethod
        def test_ColormapSelection():
            from frheed.utils import test_widget
            wid, app = test_widget(ColormapSelection, block=True)
                
        @staticmethod
        def test_ColormapMenu():
            menu = ColormapMenu()
            assert isinstance(menu, QMenu), "ColormapMenu failed"
            
        @staticmethod
        def test_get_cmap_array():
            w, h = CMAP_W, CMAP_H
            s = get_cmap_array("Spectral", CMAP_H)
            assert (h, w, 3) == s.shape, f"shape = {s.shape}"
    
    tests()
