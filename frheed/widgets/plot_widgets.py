"""
Widgets for plotting data in PyQt.
"""

import logging
from typing import Optional, Union

import numpy as np
import pyqtgraph as pg  # import *after* PyQt5
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QColor, QPixmap
from PyQt5.QtWidgets import (QAction, QCheckBox, QDoubleSpinBox,
                             QGraphicsPixmapItem, QGridLayout, QLabel,
                             QMenuBar, QPushButton, QSizePolicy, QWidget)

import frheed.utils as utils
from frheed.calcs import apply_cutoffs, calc_fft, detect_peaks
from frheed.image_processing import apply_cmap, ndarray_to_qpixmap
from frheed.widgets.camera_widget import DEFAULT_CMAP
from frheed.widgets.common_widgets import HSpacer, VisibleSplitter

# https://pyqtgraph.readthedocs.io/en/latest/_modules/pyqtgraph.html?highlight=setConfigOption
_PG_CFG = {
    "leftButtonPan": True,
    "foreground": (0, 0, 0, 255),
    "background": (0, 0, 0, 0),  # makes the background transparent
    "antialias": False,
    "editorCommand": None,
    "useWeave": False,
    "weaveDebug": True,
    "exitCleanup": True,
    "enableExperimental": False,
    "crashWarning": True,
    "imageAxisOrder": "col-major",
    "useOpenGL": False,
}
_PG_PLOT_STYLE = {
    "tickTextWidth": 30,
    "tickTextHeight": 18,
    "autoExpandTextSpace": True,
    "tickFont": None,
    "stopAxisAtTick": (False, False),  ## Check this one
    "showValues": True,
    "tickLength": 5,
    "maxTickLevel": 2,
    "maxTextLevel": 2,
}
_PG_AXES = ("left", "bottom", "right", "top")
_AXIS_COLOR = QColor("black")
_DEFAULT_SIZE = (800, 600)
_MIN_FFT_PEAK_POS = 0.5
_CURVE_MENU_TITLE = "View Lines"
_ITALIC_COORDS = True


def init_pyqtgraph(use_opengl: bool = False) -> None:
    """Set up the pyqtgraph configuration options"""
    for k, v in _PG_CFG.items():
        try:
            pg.setConfigOption(k, v)
        except Exception:
            logging.exception("Failed to set pyqtgraph config %s = %s", k, v)


class PlotWidget(QWidget):
    """The base plot widget for embedding in PyQt5"""

    curve_added = pyqtSignal(str)
    curve_removed = pyqtSignal(str)
    curve_toggled = pyqtSignal(str, bool)
    data_changed = pyqtSignal(str)

    def __init__(
        self,
        parent: QWidget = None,
        popup: bool = False,
        name: Optional[str] = None,
        title: Optional[str] = None,
        show_menubar: bool = True,
    ):
        super().__init__(parent)
        self._parent = parent
        self.name = name
        self.title = title
        self.show_menubar = show_menubar

        # Settings
        init_pyqtgraph()

        # Create layout
        self.layout = QGridLayout()
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(4)
        self.setLayout(self.layout)

        # Create plot widget
        self.plot_widget = pg.PlotWidget(
            self, title=title, background=_PG_CFG["background"]
        )
        for ax in [self.plot_widget.getAxis(a) for a in _PG_AXES]:
            ax.setPen(_AXIS_COLOR)
            ax.setStyle(**{**_PG_PLOT_STYLE, **{"tickFont": self.font()}})

        # Create menubar with transparent background
        self.menubar = QMenuBar(self)
        self.menubar.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        self.setStyleSheet(
            self.styleSheet() + "QMenuBar { background-color: transparent; }"
        )

        # Create menu for showing/hiding curves
        self.curve_menu = self.menubar.addMenu(_CURVE_MENU_TITLE)
        # self.curve_menu.setStyleSheet(self.curve_menu.styleSheet() + "QMenu { font-weight: bold; }")

        # Create cursor label
        self.cursor_label = QLabel()
        self.cursor_label.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        self.cursor_label.setMinimumWidth(64)
        if _ITALIC_COORDS:
            self.cursor_label.setStyleSheet(
                self.cursor_label.styleSheet() + "font-style: italic"
            )

        # Attributes to be assigned/updated later
        self.plot_items = {}

        # Add widgets (leave space in the middle for other widgets)
        self.layout.addWidget(self.menubar, 0, 0, 1, 1, Qt.AlignLeft)
        self.layout.addWidget(self.cursor_label, 0, 7, 1, 1)
        self.layout.addWidget(self.plot_widget, 1, 0, 1, 8)

        # Show or hide the menubar
        self.menubar.setVisible(self.show_menubar)

        # Connect signal for cursor movement
        # NOTE: Must assign to variable so it doesn't get garbage collected
        self.cursor_proxy = pg.SignalProxy(
            self.plot_item.scene().sigMouseMoved,
            rateLimit=60,
            slot=self.show_cursor_position,
        )

        # Hide options from the context menu that seem to be broken
        # menus = [self.plot_item.vb.menu, self.plot_item.ctrlMenu, self.plot_item.vb.scene().contextMenu[0]]
        # for menu in menus:
        #     for action in menu.actions():
        #         print(action.text())
        self.plot_item.ctrlMenu.menuAction().setVisible(False)

        # Show widget
        if popup:
            self.setWindowFlags(Qt.Window)
            self.show()
            self.raise_()
            self.setWindowTitle(str(name) if name is not None else "Plot")
            self.resize(*_DEFAULT_SIZE)

    def closeEvent(self, event) -> None:
        self.setParent(None)
        self.plot_widget.close()

    def leaveEvent(self, event) -> None:
        self.cursor_label.setText("")

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
        """Get an existing plot item."""
        color = utils.get_qcolor(color)
        return self.plot_items.get(color.name())

    @pyqtSlot(str)
    def add_curve(self, color: Union[QColor, str, tuple]) -> pg.PlotCurveItem:
        """Add a curve to the plot."""
        # Raise error if curve already exists
        color = utils.get_qcolor(color)
        if self.plot_items.get(color.name()) is not None:
            raise AttributeError(f"{color.name()} curve already exists.")

        # Create curve (named after the color hex) and return it
        pen = utils.get_qpen(color, cosmetic=True)
        curve = pg.PlotCurveItem(pen=pen, name=color.name())
        self.plot_items[color.name()] = curve
        self.plot_item.addItem(curve)

        # Emit curve_added and connect data update signal so FFT can update
        self.curve_added.emit(color.name())
        curve.sigPlotChanged.connect(lambda c: self.data_changed.emit(color.name()))

        # Create action in curve_menu
        self.add_curve_menu_action(color.name())

        return curve

    @pyqtSlot(str)
    def get_or_add_curve(self, color: Union[QColor, str, tuple]) -> pg.PlotCurveItem:
        """Get a curve or add it if it doesn't exist."""
        # Return curve if it already exists
        color = utils.get_qcolor(color)
        if self.plot_items.get(color.name()) is not None:
            return self.get_curve(color)

        # Create curve
        return self.add_curve(color)

    @pyqtSlot(str)
    def remove_curve(self, color: Union[QColor, str, tuple]) -> None:
        """Remove a curve from the plot."""
        # Remove the curve from the plot
        color = utils.get_qcolor(color)
        self.plot_item.removeItem(self.get_curve(color))

        # Remove from storage
        self.plot_items.pop(color.name(), None)

        # Remove action from menu
        action = self._get_menu_action(color.name())
        action.setParent(None) if action is not None else None

        # Emit curve_removed so FFT can update
        self.curve_removed.emit(color.name())

    @pyqtSlot(object)
    def show_cursor_position(self, event: object) -> None:
        # Get position of event
        pos = event[0]

        # Get local cursor position and update label
        try:
            cursor = self.plot_item.vb.mapSceneToView(pos)
            x, y = cursor.x(), cursor.y()
            self.cursor_label.setText(f"{x:.2f}, {y:.2f}")

        # Catch exception if the plot is collapsed in splitter
        except:
            pass

    @pyqtSlot(str, bool)
    def curve_menu_clicked(self, color: str, visible: bool) -> None:
        self.toggle_curve(color, visible)

    def add_curve_menu_action(self, color: str) -> QAction:
        """Add a QAction to the curve_menu for showing/hiding a curve."""
        # Check if curve exists
        action = self._get_menu_action(color)
        if action is not None:
            return action

        # Create menu item
        # 'color' should be hex value
        action = self.curve_menu.addAction(color)
        action.setCheckable(True)
        action.setChecked(True)

        # Update font color
        # TODO: Fiigure out how to do this

        # Link signal to show/hide curve
        action.toggled.connect(lambda v: self.curve_menu_clicked(color, v))

        return action

    def get_items(self) -> list:
        return self.plot_widget.listDataItems()

    def toggle_curve(
        self, color: str, visible: bool, block_signal: bool = False
    ) -> None:
        """Show or hide a curve."""
        # Get the curve
        curve = self.get_curve(color)

        # If the curve doesn't exist, return early
        if curve is None:
            return

        # Toggle the curve
        curve.setVisible(visible)

        # Emit curve_toggled signal
        self.curve_toggled.emit(color, visible) if not block_signal else None

    def _get_menu_action(self, color: str) -> Union[QAction, None]:
        return next((i for i in self.curve_menu.actions() if i.text() == color), None)


class LinePlotWidget(PlotWidget):
    def __init__(
        self,
        parent: PlotWidget,
        popup: bool = False,
        name: Optional[str] = None,
        title: Optional[str] = None,
        show_menubar: bool = True,
    ) -> None:
        super().__init__(
            parent=parent,
            popup=popup,
            name=name,
            title=title,
            show_menubar=show_menubar,
        )

        # Update labels
        self.bottom.setLabel("Time", units="s")
        self.left.setLabel("Intensity (counts)")

        # Create LinearRegionItem for adjusting FFT window
        b = pg.mkBrush((0, 0, 255, 10))
        hb = pg.mkBrush((0, 0, 255, 25))
        self.fft_window = pg.LinearRegionItem(brush=b, hoverBrush=hb, bounds=(0, None))
        self.plot_item.addItem(self.fft_window)

        # Create input for manually setting min/max
        self.fft_min_input = QDoubleSpinBox()
        self.fft_min_input.setValue(self.fft_bounds[0])
        self.fft_max_input = QDoubleSpinBox()
        self.fft_max_input.setValue(self.fft_bounds[1])
        for box in [self.fft_min_input, self.fft_max_input]:
            box.setMinimum(0)
            box.setMaximum(9999)
            box.setDecimals(2)
            box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

        # Create labels
        self.fft_min_label = QLabel("Min:")
        self.fft_max_label = QLabel("Max:")
        [
            w.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            for w in (self.fft_min_label, self.fft_max_label)
        ]

        # Create checkbox for autoscale max
        self.auto_fft_max_checkbox = QCheckBox("Autoscale max")
        self.auto_fft_max_checkbox.setChecked(True)

        # Add widgets
        self.layout.addWidget(self.fft_min_label, 0, 1, 1, 1)
        self.layout.addWidget(self.fft_min_input, 0, 2, 1, 1)
        self.layout.addWidget(self.fft_max_label, 0, 3, 1, 1)
        self.layout.addWidget(self.fft_max_input, 0, 4, 1, 1)
        self.layout.addWidget(self.auto_fft_max_checkbox, 0, 5, 1, 1)

        # Connect signal for fft_window bounds changing
        self.fft_window.sigRegionChanged.connect(self.fft_window_dragged)
        self.fft_min_input.valueChanged.connect(self.set_fft_min)
        self.fft_max_input.valueChanged.connect(self.set_fft_max)

    @property
    def fft_bounds(self) -> list:
        return sorted([line.getXPos() for line in self.fft_window.lines])

    @property
    def auto_fft_max(self) -> bool:
        return self.auto_fft_max_checkbox.isChecked()

    @pyqtSlot()
    def fft_window_dragged(self) -> None:
        """Update the FFT window region inputs."""
        [b.blockSignals(True) for b in [self.fft_min_input, self.fft_max_input]]
        self.fft_min_input.setValue(self.fft_bounds[0])
        self.fft_max_input.setValue(self.fft_bounds[1])
        [b.blockSignals(False) for b in [self.fft_min_input, self.fft_max_input]]

    @pyqtSlot(float)
    def set_fft_min(self, x: float) -> None:
        """Set the minimum position of the FFT window."""
        self.fft_window.blockLineSignal = True
        if not self.fft_window.moving:
            self.fft_window.setRegion((x, self.fft_bounds[1]))
        self.fft_window.blockLineSignal = False

    @pyqtSlot(float)
    def set_fft_max(self, x: float) -> None:
        """Set the maximum position of the FFT window."""
        self.fft_window.blockLineSignal = True
        if not self.fft_window.moving:
            self.fft_window.setRegion((self.fft_bounds[0], x))
        self.fft_window.blockLineSignal = False

    def get_data(self, color: str, ignore_window: bool = False) -> tuple:
        """Get data from one of the lines."""
        # TODO


class FFTPlotWidget(PlotWidget):
    """Widget for showing FFT data from another plot."""

    def __init__(
        self,
        parent: PlotWidget,
        popup: bool = False,
        name: Optional[str] = None,
        title: Optional[str] = None,
        show_menubar: bool = True,
        autofind_peaks: bool = True,
        low_freq_cutoff: Optional[float] = _MIN_FFT_PEAK_POS,
    ) -> None:
        super().__init__(
            parent=parent,
            popup=popup,
            name=name,
            title=title,
            show_menubar=show_menubar,
        )
        self._parent = parent
        self.autofind_peaks = autofind_peaks
        self.low_freq_cutoff = low_freq_cutoff
        self.vlines = {}

        # Create corresponding plot items
        [self.add_curve(color) for color in self._parent.plot_items]

        # Connect signal so that curves are added/removed correspondingly
        self._parent.curve_added.connect(self.add_curve)
        self._parent.curve_removed.connect(self.remove_curve)
        self._parent.data_changed.connect(self.plot_fft)
        self.curve_toggled.connect(self.toggle_vlines)

        # Update axes
        self.bottom.setLabel("Frequency", units="Hz")

    @pyqtSlot(str)
    def plot_fft(self, color: str) -> None:
        # Don't plot if the curve is not visible, and hide all vertical lines
        fft_curve = self.get_curve(color)
        if not fft_curve.isVisible():
            [self.plot_item.removeItem(line) for line in self.vlines.get(color, [])]
            return

        # Get QColor
        color = utils.get_qcolor(color)

        # Get parent & FFT curves
        parent_curve = self._parent.get_curve(color)

        # Get curve data
        x, y = parent_curve.getData()

        # Apply cutoffs
        minval, maxval = self._parent.fft_bounds
        x, y = apply_cutoffs(x=x, y=y, minval=minval, maxval=maxval)

        # Try to compute FFT
        # NOTE: If data isn't copied, it will mess with the original curve data
        freq, psd = calc_fft(x.copy(), y.copy())
        if freq is None or psd is None:
            return

        # Cutoff low frequency peak
        freq, psd = self._cutoff_low_freq(freq, psd)

        # Update corresponding curve data
        try:
            fft_curve.setData(freq, psd)
        except RuntimeError:
            pass

        # Show peak positions, if option is selected
        self.detect_and_show_peaks(
            freq, psd, color.name()
        ) if self.autofind_peaks else None

    @pyqtSlot(str, bool)
    def toggle_vlines(self, color: str, visible: bool) -> None:
        """Show/hide lines for a particular curve."""
        [line.setVisible(visible) for line in self.vlines.get(color, [])]

    def detect_and_show_peaks(
        self, x: list, y: list, color: Optional[str] = None
    ) -> None:
        # Find peaks
        peak_positions = detect_peaks(x, y, _MIN_FFT_PEAK_POS)
        if peak_positions is None:
            return

        # Clear vlines for current color
        if color is not None:
            color = utils.get_qcolor(color).name()
            lines = self.vlines.get(color, [])
            [self.plot_item.removeItem(line) for line in lines]

        # Add lines
        pen = pg.mkPen()
        pen.setStyle(Qt.DashLine)
        pen.setColor(utils.get_qcolor(color)) if color is not None else None
        new_lines = [self.plot_item.addLine(x=x, pen=pen) for x in peak_positions]
        if color is not None:
            self.vlines[color] = new_lines

    def _cutoff_low_freq(self, x: list, y: list) -> tuple:
        return apply_cutoffs(x=x, y=y, minval=self.low_freq_cutoff, maxval=None)


class LineProfileWidget(PlotWidget):
    """Widget for displaying linear profile as a 2D time series"""

    def __init__(
        self,
        parent: FFTPlotWidget,
        popup: bool = False,
        name: Optional[str] = None,
        title: Optional[str] = None,
        show_menubar: bool = True,
    ) -> None:
        super().__init__(
            parent=parent,
            popup=popup,
            name=name,
            title=title,
            show_menubar=show_menubar,
        )

        # Update labels
        self.bottom.setLabel("Position")
        self.left.setLabel("Intensity (Counts)")


class LineScanPlotWidget(PlotWidget):
    """Widget for displaying linear profile as a 2D time series"""

    def __init__(
        self,
        parent: FFTPlotWidget,
        popup: bool = False,
        name: Optional[str] = None,
        title: Optional[str] = None,
        show_menubar: bool = True,
    ) -> None:
        super().__init__(
            parent=parent,
            popup=popup,
            name=name,
            title=title,
            show_menubar=show_menubar,
        )

        # Update labels
        self.bottom.setLabel("Time", units="s")
        self.left.setLabel("Position")

        # Image placeholders
        # TODO: Handle line scans from multiple different lines
        self._image: Optional[np.ndarray] = None
        self._pixmap_item: Optional[QGraphicsPixmapItem] = None

        # TESTING
        # self.set_image(np.random.rand(100, 100))

    @property
    def image(self) -> Union[np.ndarray, None]:
        return self._image

    @image.setter
    def image(self, image: np.ndarray) -> None:
        # Apply colormap
        cmapped = apply_cmap(image, DEFAULT_CMAP)

        # Update pixmap
        self.pixmap = ndarray_to_qpixmap(cmapped)

        # Store image
        self._image = image

    @property
    def pixmap_item(self) -> QGraphicsPixmapItem:
        return self._pixmap_item

    @pixmap_item.setter
    def pixmap_item(self, pixmap: Union[QPixmap, QGraphicsPixmapItem]) -> None:
        if isinstance(pixmap, QPixmap) and self._pixmap_item is not None:
            # Replace the pixmap
            self._pixmap_item.setPixmap(pixmap)

        elif isinstance(pixmap, QPixmap) and self._pixmap_item is None:
            self._pixmap_item = QGraphicsPixmapItem(pixmap)
            # Add the image to the plot
            self.plot_item.addItem(self._pixmap_item)

        elif isinstance(pixmap, QGraphicsPixmapItem) and self._pixmap_item is None:
            self._pixmap_item = pixmap
            # Add the image to the plot
            self.plot_item.addItem(self._pixmap_item)

        elif isinstance(pixmap, QGraphicsPixmapItem) and self._pixmap_item is not None:
            self._pixmap_item.pixmap().swap(pixmap.pixmap())

        else:
            raise TypeError(
                f"Expected QPixmap or QGraphicsPixmapItem, got {type(pixmap)}"
            )

    @property
    def pixmap(self) -> Union[QPixmap, None]:
        if self.pixmap_item is not None:
            return self.pixmap_item.pixmap()
        return None

    @pixmap.setter
    def pixmap(self, pixmap: QPixmap) -> None:
        self.pixmap_item = pixmap

    def set_image(self, image: np.ndarray) -> None:
        """Set the current image."""
        # Use property setter to update the item and pixmap
        self.image = image

        # Scale the bounds properly
        h, w = image.shape[:2]
        self.plot_item.setXRange(
            0, w * 1.05, padding=0
        )  # default between 0.02 and 0.1 if not specified
        self.plot_item.setYRange(0, h * 1.02, padding=0)


class GrowthRatePlotWidget(PlotWidget):
    """Widget for selecting visible lines on a plot."""

    def __init__(
        self,
        parent: FFTPlotWidget,
        popup: bool = False,
        name: Optional[str] = None,
        title: Optional[str] = None,
        show_menubar: bool = True,
    ) -> None:
        super().__init__(
            parent=parent,
            popup=popup,
            name=name,
            title=title,
            show_menubar=show_menubar,
        )

        # Update labels
        self.bottom.setLabel("Time", units="s")
        self.left.setLabel("Growth Rate (ML/s)")


class PlotGridWidget(QWidget):
    closed = pyqtSignal()

    """ Widget for containing the live RHEED plots and plot transformations. """

    def __init__(self, parent=None, title: Optional[str] = None, popup: bool = True):
        super().__init__(parent)
        self._parent = parent

        # Create layout
        self.layout = QGridLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(4)
        self.setLayout(self.layout)

        # Create controls layout
        self.controls_layout = QGridLayout()
        self.controls_layout.setContentsMargins(4, 4, 4, 4)
        self.controls_layout.setSpacing(4)

        # Create menubar
        self.menubar = QMenuBar(self)
        self.menubar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.curve_menu = self.menubar.addMenu(_CURVE_MENU_TITLE)

        # Create controls buttons
        self.start_button = QPushButton("Start")  # TODO: Add icon
        self.stop_button = QPushButton("Stop")  # TODO: Add icon

        # Create plots layout
        self.plots_layout = QGridLayout()
        self.plots_layout.setContentsMargins(8, 8, 8, 8)
        self.plots_layout.setSpacing(4)

        # Create plot widgets
        self.region_plot = LinePlotWidget(
            parent=self, popup=False, title="Region Intensity", show_menubar=False
        )
        self.region_fft_plot = FFTPlotWidget(
            parent=self.region_plot,
            popup=False,
            title="Region Intensity FFT",
            show_menubar=False,
        )
        self.growth_rate_plot = GrowthRatePlotWidget(
            parent=self.region_fft_plot,
            popup=False,
            title="Growth Rate",
            show_menubar=False,
        )
        self.profile_plot = LineProfileWidget(
            parent=self, popup=False, title="1D Line Profile", show_menubar=False
        )
        # self.profile_fft_plot = FFTPlotWidget(parent=self.profile_plot, popup=False,
        #                                       title="Line Profile FFT", show_menubar=False)
        self.line_scan_plot = LineScanPlotWidget(
            parent=self, popup=False, title="2D Line Scan", show_menubar=False
        )
        self.plot_widgets = [
            self.region_plot,
            self.region_fft_plot,
            self.growth_rate_plot,
            self.profile_plot,
            # self.profile_fft_plot,
            self.line_scan_plot,
        ]
        [setattr(w, "curve_menu", self.curve_menu) for w in self.plot_widgets]

        # Create containers for plots
        color, hover = "lightGrey", "grey"
        self.main_splitter = VisibleSplitter(color, hover, orientation=Qt.Horizontal)
        self.region_plots_splitter = VisibleSplitter(
            color, hover, orientation=Qt.Vertical
        )
        self.profile_plots_splitter = VisibleSplitter(
            color, hover, orientation=Qt.Vertical
        )

        # Add items to main layout
        self.layout.addWidget(self.menubar, 0, 0, 1, 1)
        self.layout.addLayout(self.controls_layout, 1, 0, 1, 1)
        self.layout.addLayout(self.plots_layout, 2, 0, 1, 1)
        self.controls_layout.addWidget(self.start_button, 0, 0, 1, 1)
        self.controls_layout.addWidget(self.stop_button, 0, 1, 1, 1)
        self.controls_layout.addItem(HSpacer(), 0, 2, 1, 1)
        self.layout.addWidget(self.main_splitter, 2, 0, 1, 1)
        self.main_splitter.addWidget(self.region_plots_splitter)
        self.main_splitter.addWidget(self.profile_plots_splitter)
        [
            self.region_plots_splitter.addWidget(w)
            for w in (self.region_plot, self.region_fft_plot, self.growth_rate_plot)
        ]
        [
            self.profile_plots_splitter.addWidget(w)
            for w in (self.profile_plot, self.line_scan_plot)
        ]

        # Connect signals
        for widget in self.plot_widgets:
            widget.curve_toggled.connect(self.toggle_all_curves)

        # Resize splitter
        self.main_splitter.setSizes([350, 350])

        # Show widget
        _DEFAULT_SIZE = (800, 600)
        if popup:
            self.setWindowFlags(Qt.Window)
            self.show()
            self.raise_()
            self.setWindowTitle(str(title) if title is not None else "Plots")
            self.resize(*_DEFAULT_SIZE)

    def closeEvent(self, event) -> None:
        self.closed.emit()
        super().closeEvent(event)

    @pyqtSlot(str, bool)
    def toggle_all_curves(self, color: str, visible: bool) -> None:
        [
            wid.toggle_curve(color, visible, block_signal=True)
            for wid in self.plot_widgets
        ]

    @pyqtSlot(object)
    def remove_curves(self, shape) -> None:
        """Remove curves from plots."""
        color = shape.color.name()
        [wid.remove_curve(color) for wid in self.plot_widgets]


if __name__ == "__main__":

    def test():
        from frheed.utils import test_widget

        return test_widget(PlotGridWidget, block=True, parent=None)

    widget, app = test()
