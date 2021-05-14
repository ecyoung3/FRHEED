# -*- coding: utf-8 -*-
"""
Widgets for RHEED analysis.
"""

from typing import Union

from PyQt5.QtWidgets import (
    QWidget,
    QGridLayout,
    QSizePolicy,
    
    )
from PyQt5.QtCore import (
    Qt,
    pyqtSlot,
    
    )

from FRHEED.widgets.camera_widget import VideoWidget
from FRHEED.cameras.FLIR import FlirCamera
from FRHEED.cameras.USB import UsbCamera
from FRHEED.widgets.plot_widgets import PlotWidget
from FRHEED.widgets.canvas_widget import CanvasShape, CanvasLine
from FRHEED.widgets.selection_widgets import CameraSelection
from FRHEED.utils import snip_lists


class RHEEDWidget(QWidget):
    _initialized = False
    
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        
        # Settings
        self.setSizePolicy(QSizePolicy.MinimumExpanding,
                           QSizePolicy.MinimumExpanding)
        
        # Create the layout
        self.layout = QGridLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(4)
        self.setLayout(self.layout)
        
        # Create camera selection widget and wait for choice
        self.setVisible(False)
        self.cam_selection = CameraSelection()
        self.cam_selection.camera_selected.connect(self._init_ui)
        self.cam_selection.raise_()
        
    @pyqtSlot()
    def _init_ui(self) -> None:
        """ Finish UI setup after selecting a camera. """
        # Show the widget
        self.setVisible(True)
        
        # Create the camera widget
        camera = self.cam_selection._cam
        self.camera_widget = VideoWidget(camera, parent=self)
        self.camera_widget.setSizePolicy(QSizePolicy.MinimumExpanding,
                                         QSizePolicy.MinimumExpanding)
        
        # Create the plot widgets
        self.region_plot = PlotWidget(parent=self, popup=True, name="Regions")
        self.profile_plot = PlotWidget(parent=self, popup=True, name="Line Profiles")
        
        # Add widgets to layout
        self.layout.addWidget(self.camera_widget, 0, 0, 1, 1)
        self.layout.setRowStretch(0, 1)
        self.layout.setColumnStretch(0, 1)
        
        # Connect signals
        self.camera_widget.analysis_worker.data_ready.connect(self.plot_data)
        self.camera_widget.display.canvas.shape_deleted.connect(self.remove_line)
        
        # Mark as initialized
        self._initialized = True
        
    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        
    def closeEvent(self, event) -> None:
        if self._initialized:
            [wid.setParent(None) for wid in [self.region_plot, self.profile_plot, self]]
            self.camera_widget.closeEvent(event)
        self.cam_selection.close()
        
    @pyqtSlot(dict)
    def plot_data(self, data: dict) -> None:
        """ Plot data from the camera """
        for color, color_data in data.items():
            if color_data["kind"] in ["rectangle", "ellipse"]:
                curve = self.region_plot.add_curve(color)
                # Catch RuntimeError if widget has been closed
                try:
                    curve.setData(*snip_lists(color_data["time"], color_data["average"]))
                except RuntimeError:
                    pass
            elif color_data["kind"] == "line":
                curve = self.profile_plot.add_curve(color)
                try:
                    curve.setData(color_data["y"][-1])
                except RuntimeError:
                    pass
                
    @pyqtSlot(object)
    def remove_line(self, shape: Union["CanvasShape", "CanvasLine"]) -> None:
        """ Remove a line from the plot it is part of """
        
        # Get the plot widget
        plot = self.profile_plot if shape.kind == "line" else self.region_plot
        
        # Remove the line
        plot.plot_widget.removeItem(plot.plot_items.pop(shape.color_name))
        self.camera_widget.analysis_worker.data.pop(shape.color_name)


if __name__ == "__main__":
    def test():
        from FRHEED.utils import test_widget
        
        return test_widget(RHEEDWidget, block=True)
        
    widget, app = test()
