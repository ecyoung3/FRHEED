"""
Commonly used subclassed PyQt6 widgets.
"""

import math
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFontMetrics
from PyQt6.QtWidgets import QFrame, QLabel, QSizePolicy, QSlider, QSpacerItem, QSplitter, QWidget

from frheed.utils import unit_string


class DoubleSlider(QSlider):
    """A QSlider that uses floating-point values instead of integers."""

    doubleValueChanged = pyqtSignal(float)

    def __init__(
        self,
        decimals: int,
        log: bool = False,
        base: float = 1.5,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)

        # Validate input
        if decimals < 0 or not isinstance(decimals, int):
            raise ValueError(
                "Number of decimals must be a positive integer;" f"got {decimals} instead"
            )

        # Store inputs
        self.decimals = min(decimals, 2)  # more than 2 decimals causes bugs
        self._log = log
        self._base = base

        # Settings
        self.setOrientation(Qt.Orientation.Horizontal)

        # Since QSlider is integer by default, the multiplier will be (1/10^n)
        # where n == # of decimals
        self._multiplier: float = 1 / (10**self.decimals)

        # Connect signal
        self.valueChanged.connect(self.emitDoubleValueChanged)

    def emitDoubleValueChanged(self) -> None:
        try:
            self.doubleValueChanged.emit(self.value())
        except AttributeError:
            # During initialization, _maximum and _minimum are not set
            pass

    def isLog(self) -> bool:
        return self._log

    def base(self) -> float:
        return self._base

    def multiplier(self) -> float:
        return self._multiplier

    def value(self) -> float:  # type: ignore[override]
        return min(max(self._to_float(super().value()), self._minimum), self._maximum)

    def minimum(self) -> float:  # type: ignore[override]
        return getattr(self, "_minimum", self._to_float(super().minimum()))

    def setMinimum(self, value: float) -> None:
        self._minimum = value
        super().setMinimum(self._to_int(value))

    def maximum(self) -> float:  # type: ignore[override]
        return getattr(self, "_maximum", self._to_float(super().maximum()))

    def setMaximum(self, value: float) -> None:
        self._maximum = value
        super().setMaximum(self._to_int(value))

    def setSingleStep(self, value: float) -> None:
        super().setSingleStep(self._to_int(value))

    def singleStep(self) -> float:  # type: ignore[override]
        return self._to_float(super().singleStep())

    def setValue(self, value: float) -> None:
        super().setValue(self._to_int(value))

    def setTickInterval(self, value: float) -> None:
        super().setTickInterval(self._to_int(value))

    def _to_int(self, value: float) -> int:
        if self.isLog():
            return int(round(math.log((value / self._multiplier), self.base())))
        return int(round(value / self._multiplier))

    def _to_float(self, value: float) -> float:
        if self.isLog():
            return float((self.base() ** value) * self._multiplier)
        return float(value * self._multiplier)


class SliderLabel(QLabel):
    """A QLabel that always shows the value of the linked slider."""

    def __init__(
        self,
        slider: QSlider,
        name: str | None = None,
        unit: str | None = None,
        precision: int | None = None,
        pad: int = 8,
    ) -> None:
        parent = slider.parent()
        if isinstance(parent, QWidget):
            super().__init__(parent)
        else:
            super().__init__()

        # Store attributes
        self.slider = slider
        self.name = name or "Slider value"
        self.unit = unit
        self.precision = precision

        # Make sure size can accommodate longest possible string
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.set_width(pad)

        # Connect slider to label so value updates constantly
        self.slider.valueChanged.connect(self.value_changed)
        self.slider.valueChanged.emit(0)

    @pyqtSlot(int)
    def value_changed(self, *args: Any) -> None:
        value = self.slider.value()
        text = unit_string(value, self.unit, precision=self.precision)
        self.setText(f"{self.name}: {text}")

    def set_width(self, pad: int) -> None:
        """Set the label width to accommodate text with specified padding"""

        # Get maximum value that can be displayed
        max_val = self.slider.maximum()

        # Get text to display
        unit_str = unit_string(max_val, self.unit, precision=self.precision)
        display_value = f"{self.name}: {unit_str}"

        # Calculate display width of the text, in pixels
        font_metrics = QFontMetrics(self.font())
        font_width = font_metrics.boundingRect(display_value).width()

        # Update fixed width
        self.setFixedWidth(font_width + pad)


class HLine(QFrame):
    """A horizontal separator line"""

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumWidth(1)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setFrameShadow(QFrame.Shadow.Plain)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)


class VLine(QFrame):
    """A vertical separator line"""

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumHeight(1)
        self.setFrameShape(QFrame.Shape.VLine)
        self.setFrameShadow(QFrame.Shadow.Plain)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)


class HSpacer(QSpacerItem):
    def __init__(self) -> None:
        super().__init__(1, 1, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)


class VSpacer(QSpacerItem):
    def __init__(self) -> None:
        super().__init__(1, 1, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)


class VisibleSplitter(QSplitter):
    def __init__(
        self, color: str, hover_color: str | None = None, *args: Any, **kwargs: Any
    ) -> None:
        super().__init__(*args, **kwargs)
        style = (
            self.styleSheet()
            + f"""
                                QSplitter::handle:horizontal:!pressed {{ 
                                    border-left: 1px solid {color};
                                    }}
                                QSplitter::handle:horizontal:pressed {{ 
                                    border-left: 1px solid {hover_color or color};
                                    }}
                                QSplitter::handle:vertical:!pressed {{
                                    border-bottom: 1px solid {color};
                                    }}
                                QSplitter::handle:vertical:pressed {{
                                    border-bottom: 1px solid {hover_color or color};
                                    }}
                                """
        )
        self.setStyleSheet(style)
