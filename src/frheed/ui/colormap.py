"""UI components for previewing and selecting colormaps."""

from __future__ import annotations

import enum
import functools
from collections.abc import Sequence
from typing import TYPE_CHECKING

import matplotlib.colors
import matplotlib.pyplot as plt
import numpy as np
from PyQt6 import QtCore, QtGui, QtWidgets

if TYPE_CHECKING:
    import matplotlib.colors


Colormap = matplotlib.colors.Colormap


class ColormapFamily(enum.Enum):
    """A family of visually-similar colormaps.

    https://matplotlib.org/stable/gallery/color/colormap_reference.html
    """

    PERCEPTUALLY_UNIFORM_SEQUENTIAL = ("viridis", "plasma", "inferno", "magma", "cividis")
    SEQUENTIAL = (
        "Greys",
        "Purples",
        "Blues",
        "Greens",
        "Oranges",
        "Reds",
        "YlOrBr",
        "YlOrRd",
        "OrRd",
        "PuRd",
        "RdPu",
        "BuPu",
        "GnBu",
        "PuBu",
        "YlGnBu",
        "PuBuGn",
        "BuGn",
        "YlGn",
    )
    SEQUENTIAL_2 = (
        "binary",
        "gist_yarg",
        "gist_gray",
        "gray",
        "bone",
        "pink",
        "spring",
        "summer",
        "autumn",
        "winter",
        "cool",
        "Wistia",
        "hot",
        "afmhot",
        "gist_heat",
        "copper",
    )
    DIVERGING = (
        "PiYG",
        "PRGn",
        "BrBG",
        "PuOr",
        "RdGy",
        "RdBu",
        "RdYlBu",
        "RdYlGn",
        "Spectral",
        "coolwarm",
        "bwr",
        "seismic",
    )
    CYCLIC = ("twilight", "twilight_shifted", "hsv")
    QUALITATIVE = (
        "Pastel1",
        "Pastel2",
        "Paired",
        "Accent",
        "Dark2",
        "Set1",
        "Set2",
        "Set3",
        "tab10",
        "tab20",
        "tab20b",
        "tab20c",
    )
    MISCELLANEOUS = (
        "flag",
        "prism",
        "ocean",
        "gist_earth",
        "terrain",
        "gist_stern",
        "gnuplot",
        "gnuplot2",
        "CMRmap",
        "cubehelix",
        "brg",
        "gist_rainbow",
        "rainbow",
        "jet",
        "turbo",
        "nipy_spectral",
        "gist_ncar",
    )


def is_reversed_colormap_name(cmap_name: str) -> bool:
    """Returns whether or not a colormap name is the reversed version of a colormap.

    Reversed colormap names end with "_r" - see the matplotlib documentation for details.

    https://matplotlib.org/stable/gallery/color/colormap_reference.html#reversed-colormaps
    """
    return cmap_name.endswith("_r")


def get_reversed_colormap_name(cmap_name: str) -> str:
    """Returns the name for the reversed version of a colormap.

    This is done by appending "_r" to the colormap name if it does not already end with "_r".

    https://matplotlib.org/stable/gallery/color/colormap_reference.html#reversed-colormaps
    """
    # Any matplotlib colormap can be reversed by appending "_r" to its name
    return cmap_name if is_reversed_colormap_name(cmap_name) else f"{cmap_name}_r"


def get_colormap(cmap_name: str, lut: int = 256, reversed: bool = False) -> Colormap:
    """Returns the pyplot colormap with the given name.

    This function is a simple wrapper for `matplotlib.pyplot.get_cmap()`.

    Args:
        cmap_name: The colormap name, which should be a registered pyplot colormap.
        lut: The number of colors in the colormap. If generating a colormap to apply to images, this
            number should be chosen based on the bit count of the image color space; for example, an
            8-bit image should use a colormap with 2^8 = 256 colors.
    """
    cmap_name = cmap_name if not reversed else get_reversed_colormap_name(cmap_name)
    return plt.get_cmap(cmap_name, lut)


def list_colormaps() -> list[str]:
    """Returns the names of all available colormaps."""
    return plt.colormaps()


@functools.lru_cache
def get_colors(cmap_name: str, lut: int = 256, reversed: bool = False) -> list[QtGui.QColor]:
    """Returns a list of the colors in the given colormap."""
    cmap = plt.get_cmap(cmap_name, lut=lut)
    rgba_array = plt.cm.ScalarMappable(cmap=cmap).to_rgba(np.linspace(0, 1, lut), bytes=True)
    colors = [QtGui.QColor(*rgb) for rgb in rgba_array]
    return colors


@functools.lru_cache
def get_colortable(cmap_name: str, reversed: bool = False) -> list[int]:
    """Returns a 256-item RGB integer colortable for the given colormap."""
    return [color.rgb() for color in get_colors(cmap_name, lut=256, reversed=reversed)]


class ColormapImage(QtGui.QImage):
    """An image representation of a colormap."""

    def __init__(
        self,
        cmap: Colormap | str,
        width: int = 128,
        height: int = 128,
    ) -> None:
        if isinstance(cmap, str):
            cmap = plt.get_cmap(cmap, lut=width)

        self._cmap = cmap

        # Represent the colormap as an array with the given size
        row = np.linspace(0, 1, width)
        rgba = plt.cm.ScalarMappable(cmap=cmap).to_rgba(np.tile(row, (height, 1)), bytes=True)
        bytes_per_line = rgba.strides[0]
        image_format = QtGui.QImage.Format.Format_RGBA8888
        super().__init__(rgba.data, width, height, bytes_per_line, image_format)

    def get_colormap(self) -> Colormap:
        """Returns the colormap the image represents."""
        return self._cmap

    def get_colormap_name(self) -> str:
        """Returns the name of the colormap the image represents."""
        return self._cmap.name

    def resize(self, width: int, height: int) -> None:
        """Resize the image to the given dimensions."""
        resized_image = self.scaled(width, height)
        self.swap(resized_image)

    def resized(self, width: int, height: int) -> ColormapImage:
        """Returns a copy of the image resized to the given dimensions."""
        return ColormapImage(self.get_colormap(), width, height)

    def to_pixmap(self) -> QtGui.QPixmap:
        """Returns the colormap image as a pixmap."""
        return QtGui.QPixmap.fromImage(self)

    def to_icon(self) -> QtGui.QIcon:
        """Returns the colormap image as an icon."""
        return QtGui.QIcon(self.to_pixmap())


class ColormapAction(QtGui.QAction):
    """An action used to select a colormap."""

    def __init__(self, cmap: Colormap | str, parent: QtWidgets.QWidget | None = None) -> None:
        cmap_image = ColormapImage(cmap)
        cmap_icon = cmap_image.to_icon()
        cmap_name = cmap_image.get_colormap_name()
        super().__init__(cmap_icon, cmap_name, parent)

        # Store the colormap name as item data for passing around via signals and slots
        self._cmap_name = cmap_name
        self.setData(cmap_name)

        # Show a 256x32 image of the colormap as its tooltip
        # https://stackoverflow.com/a/34300771/10342097
        # TODO(ecyoung3): There is still a slight margin on the tooltip - consider creating a
        #   custom widget instead and intercepting the ToolTip event.
        image_data = QtCore.QByteArray()
        image_buffer = QtCore.QBuffer(image_data)
        cmap_image.scaled(256, 32).save(image_buffer, "PNG", 100)
        image_data_base64 = image_data.toBase64().data().decode()
        tooltip = f"<img src='data:image/png;base64, {image_data_base64}'>"
        self.setToolTip(tooltip)

    def get_colormap_name(self) -> str:
        """Returns the name of the colormap associated with this action."""
        return self._cmap_name


class ColormapsMenu(QtWidgets.QMenu):
    """A menu of colormaps."""

    # Signal emitted when a colormap is selected
    colormap_selected = QtCore.pyqtSignal(str)

    def __init__(
        self,
        title: str,
        cmap_names: Sequence[str],
        include_reversed: bool = True,
        action_group: QtGui.QActionGroup | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        """Initializes the colormap menu.

        Args:
            title: The text to display for the menu.
            cmap_names: The names of all colormaps to include in the menu.
            include_reversed: Whether to include reversed versions of all colormaps in the menu.
            action_group: The action group to add all colormap actions to, for example if only one
                colormap from the group should be selected at any given time. If none is provided,
                the colormap actions will not belong to a group.
            parent: The widget to set as the parent of the menu.
        """
        super().__init__(title, parent)

        # Add actions for each of the colormaps to the menu and to the action group if necessary
        actions: list[ColormapAction] = []
        for cmap_name in cmap_names:
            actions.append(ColormapAction(cmap_name, self))
            if include_reversed and not is_reversed_colormap_name(cmap_name):
                actions.append(ColormapAction(get_reversed_colormap_name(cmap_name), self))

        self.addActions(actions)

        # Actions should be checkable if they belong to an action group
        if action_group is not None:
            for action in actions:
                action.setCheckable(True)
                action_group.addAction(action)

        # Enable tooltips so the user can preview the colormap when hovering over it
        self.setToolTipsVisible(True)

        # Emit the `colormap_changed` signal when an action is clicked
        self.triggered.connect(self.on_action_triggered)

    @classmethod
    def for_family(
        cls,
        family: ColormapFamily,
        include_reversed: bool = True,
        action_group: QtGui.QActionGroup | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> ColormapsMenu:
        """Returns a colormap menu containing colormaps in the given family."""
        # Generate the menu title based on the family name, e.g. "SEQUENTIAL_2" -> "Sequential (2)"
        title_parts = family.name.split("_")
        title = " ".join(f"({part})" if part.isnumeric() else part.title() for part in title_parts)
        cmap_names = family.value
        return cls(title, cmap_names, include_reversed, action_group, parent)

    @QtCore.pyqtSlot(QtGui.QAction)
    def on_action_triggered(self, action: QtGui.QAction) -> None:
        """Emits the colormap name associated with the triggered action."""
        if isinstance(action, ColormapAction):
            self.colormap_selected.emit(action.get_colormap_name())


class ColormapFamiliesMenu(QtWidgets.QMenu):
    """A menu containing submenus for each family of colormaps."""

    # Signal emitted when a colormap is selected
    colormap_selected = QtCore.pyqtSignal(str)

    def __init__(
        self,
        include_reversed: bool = True,
        title: str | None = "&Colormaps",
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(title, parent)

        # Create submenus for all colormap families, using an exclusive action group so that only
        # one colormap can be selected at any given time
        action_group = QtGui.QActionGroup(self)
        action_group.setExclusive(True)
        for family in ColormapFamily:
            submenu = ColormapsMenu.for_family(family, include_reversed, action_group, self)

            # Pass through the `colormap_selected` signal from the submenu
            self.addMenu(submenu)
            submenu.colormap_selected.connect(self.colormap_selected.emit)
