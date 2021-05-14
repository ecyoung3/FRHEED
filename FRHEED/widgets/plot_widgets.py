# -*- coding: utf-8 -*-
"""
Widgets for plotting data in PyQt.
"""

from typing import Union, Optional

import numpy as np

from PyQt5.QtWidgets import (
    QWidget,
    QGridLayout,
    QComboBox,
    
    )
from PyQt5.QtGui import (
    QColor,
    
    )
from PyQt5.QtCore import (
    Qt,
    
    )

import pyqtgraph as pg  # import *after* PyQt5

from FRHEED.utils import get_qcolor, get_qpen


# https://pyqtgraph.readthedocs.io/en/latest/_modules/pyqtgraph.html?highlight=setConfigOption
_PG_CFG = {
    "leftButtonPan":        True,
    "foreground":           (0, 0, 0, 255),
    "background":           (0, 0, 0, 0),  # makes the background transparent
    "antialias":            False,
    "editorCommand":        None,
    "useWeave":             False,
    "weaveDebug":           True,
    "exitCleanup":          True,
    "enableExperimental":   False,
    "crashWarning":         True,
    "imageAxisOrder":       "col-major",
    }
_PG_PLOT_STYLE = {
    "tickTextWidth":        30,
    "tickTextHeight":       18,
    "autoExpandTextSpace":  True,
    "tickFont":             None,
    "stopAxisAtTick":       (False, False),  ## Check this one
    "showValues":           True,
    "tickLength":           5,
    "maxTickLevel":         2,
    "maxTextLevel":         2,
    }
_PG_AXES = ("left", "bottom", "right", "top")
_AXIS_COLOR = QColor("black")


def init_pyqtgraph(use_opengl: bool = False) -> None:
    """ Set up the pyqtgraph configuration options """
    [pg.setConfigOption(k, v) for k, v in _PG_CFG.items()]
    pg.setConfigOption("useOpenGL", use_opengl)
    

class PlotWidget(QWidget):
    """ The base plot widget for embedding in PyQt5 """
    
    def __init__(
            self, 
            parent: QWidget = None, 
            popup: bool = False, 
            name: Optional[str] = None
            ):
        
        super().__init__(parent)
        self._parent = parent
        
        # Settings
        init_pyqtgraph()
        
        # Create layout
        self.layout = QGridLayout()
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(4)
        self.setLayout(self.layout)
        
        # Create plot widget
        self.plot_widget = pg.PlotWidget(self, background=_PG_CFG["background"])
        for ax in [self.plot_widget.getAxis(a) for a in _PG_AXES]:
            ax.setPen(_AXIS_COLOR)
            ax.setStyle(**{**_PG_PLOT_STYLE, **{"tickFont": self.font()}})
        
        # Create QComboBox for enabling/disabling lines

        
        # Attributes to be assigned/updated later
        self.plot_items = {}
        
        # Add widgets
        self.layout.addWidget(self.plot_widget, 0, 0, 1, 1)
        
        # Show widget
        if popup:
            self.setWindowFlags(Qt.Window)
            self.show()
            self.raise_()
            self.setWindowTitle(str(name) if name is not None else "Plot")
        
    def closeEvent(self, event) -> None:
        # TODO
        self.setParent(None)
        self.plot_widget.close()
        
    @property
    def plot_item(self) -> pg.PlotItem:
        return self.plot_widget.getPlotItem()
    
    @property
    def left(self) -> pg.AxisItem:
        return self.plot_widget.getAxis("left")
    
    @property
    def bottom(self) -> pg.AxisItem:
        return self.plot_widget.getAxis("bottom")
    
    @property
    def right(self) -> pg.AxisItem:
        return self.plot_widget.getAxis("right")
    
    @property
    def top(self) -> pg.AxisItem:
        return self.plot_widget.getAxis("top")
    
    @property
    def axes(self) -> list:
        return [getattr(self, ax) for ax in _PG_AXES]
    
    def add_curve(self, color: Union[QColor, str, tuple]) -> pg.PlotCurveItem:
        color = get_qcolor(color)
        if color.name() in self.plot_items:
            return self.plot_items[color.name()]
        pen = get_qpen(color, cosmetic=True)
        self.plot_items[color.name()] = pg.PlotCurveItem(pen=pen)
        self.plot_item.addItem(self.plot_items[color.name()])
        return self.plot_items[color.name()]
    
    def get_items(self) -> list:
        return self.plot_widget.listDataItems()
    

class PlotWidget2D(pg.ImageView):
    """ Widget for displaying linear profile as a 2D time series """
    def __init__(self, parent = None):
        pass
    
    
class PlotComboBox(QComboBox):
    pass
    
    
if __name__ == "__main__":
    def test():
        from FRHEED.utils import test_widget
        
        return test_widget(PlotWidget, block=True, parent=None)

    widget, app = test()