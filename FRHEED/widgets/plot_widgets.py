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
    pyqtSlot,
    pyqtSignal,
    
    )

import pyqtgraph as pg  # import *after* PyQt5

from FRHEED.utils import get_qcolor, get_qpen
from FRHEED.calcs import calc_fft


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
_DEFAULT_SIZE = (800, 600)


def init_pyqtgraph(use_opengl: bool = False) -> None:
    """ Set up the pyqtgraph configuration options """
    [pg.setConfigOption(k, v) for k, v in _PG_CFG.items()]
    pg.setConfigOption("useOpenGL", use_opengl)
    

class PlotWidget(QWidget):
    """ The base plot widget for embedding in PyQt5 """
    curve_added = pyqtSignal(str)
    curve_removed = pyqtSignal(str)
    data_changed = pyqtSignal(str)
    
    def __init__(
            self, 
            parent: QWidget = None, 
            popup: bool = False, 
            name: Optional[str] = None,
            title: Optional[str] = None,
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
        self.plot_widget = pg.PlotWidget(self, title=title, background=_PG_CFG["background"])
        for ax in [self.plot_widget.getAxis(a) for a in _PG_AXES]:
            ax.setPen(_AXIS_COLOR)
            ax.setStyle(**{**_PG_PLOT_STYLE, **{"tickFont": self.font()}})
        
        # Create QComboBox for enabling/disabling lines
        # TODO
        
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
            self.resize(*_DEFAULT_SIZE)
        
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
    
    def get_curve(self, color: Union[QColor, str, tuple]) -> pg.PlotCurveItem:
        """ Get an existing plot item. """
        color = get_qcolor(color)
        return self.plot_items[color.name()]
    
    @pyqtSlot(str)
    def add_curve(self, color: Union[QColor, str, tuple]) -> pg.PlotCurveItem:
        """ Add a curve to the plot. """
        # Raise error if curve already exists
        color = get_qcolor(color)
        if color.name() in self.plot_items:
            raise AttributeError(f"{color.name()} curve already exists.")
            
        # Create curve and return it
        pen = get_qpen(color, cosmetic=True)
        curve = pg.PlotCurveItem(pen=pen)
        self.plot_items[color.name()] = curve
        self.plot_item.addItem(curve)
        
        # Emit curve_added and connect data update signal so FFT can update
        self.curve_added.emit(color.name())
        curve.sigPlotChanged.connect(lambda c: self.data_changed.emit(color.name()))
        
        return curve
    
    @pyqtSlot(str)
    def get_or_add_curve(self, color: Union[QColor, str, tuple]) -> pg.PlotCurveItem:
        """ Get a curve or add it if it doesn't exist. """
        # Return curve if it already exists
        color = get_qcolor(color)
        if color.name() in self.plot_items:
            return self.get_curve(color)
        
        # Create curve
        return self.add_curve(color)
    
    @pyqtSlot(str)
    def remove_curve(self, color: Union[QColor, str, tuple]) -> None:
        """ Remove a curve from the plot. """
        self.plot_item.removeItem(self.get_curve(color))
        
        # Emit curve_removed so FFT can update
        self.curve_removed.emit(color.name())
    
    def get_items(self) -> list:
        return self.plot_widget.listDataItems()
    

class RegionIntensityPlot(PlotWidget):
    def __init__(
            self, 
            parent: PlotWidget, 
            popup: bool = False, 
            name: Optional[str] = None,
            title: Optional[str] = None,
            ) -> None:
        
        super().__init__(parent=parent, popup=popup, name=name, title=title)
        self.bottom.setLabel("Time", units="s")
        self.left.setLabel("Intensity (counts)")


class FFTPlotWidget(PlotWidget):
    """ Widget for showing FFT data from another plot. """
    def __init__(
            self, 
            parent: PlotWidget, 
            popup: bool = False, 
            name: Optional[str] = None,
            title: Optional[str] = None,
            ) -> None:
        
        super().__init__(parent=parent, popup=popup, name=name, title=title)
        self._parent = parent
        
        # Create corresponding plot items
        [self.add_curve(color) for color in self._parent.plot_items]
        
        # Connect signal so that curves are added/removed correspondingly
        self._parent.curve_added.connect(self.add_curve)
        self._parent.curve_removed.connect(self.remove_curve)
        self._parent.data_changed.connect(self.plot_fft)
        
        # Update axes
        self.bottom.setLabel("Frequency", units="Hz")
        
    @pyqtSlot(str)
    def plot_fft(self, color: str) -> None:
        # Get QColor
        color = get_qcolor(color)
        
        # Get parent & FFT curves
        parent_curve = self._parent.get_curve(color)
        fft_curve = self.get_curve(color)
        
        # Get curve data
        x, y = parent_curve.getData()
        
        # Try to compute FFT
        # NOTE: If data isn't copied, it will mess with the original curve data
        freq, psd = calc_fft(x.copy(), y.copy())
        if freq is None or psd is None:
            return
        
        # Update corresponding curve data
        try:
            fft_curve.setData(freq, psd)
        except RuntimeError:
            pass
        

class PlotWidget2D(pg.ImageView):
    """ Widget for displaying linear profile as a 2D time series """
    def __init__(self, parent = None):
        pass
        # TODO
    
    
class PlotComboBox(QComboBox):
    """ Widget for selecting visible lines on a plot. """
    pass


if __name__ == "__main__":
    def test():
        from FRHEED.utils import test_widget
        
        return test_widget(PlotWidget, block=True, parent=None)

    widget, app = test()