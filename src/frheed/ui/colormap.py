"""UI components for previewing and selecting colormaps."""

from __future__ import annotations

import enum
import functools
import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING

import matplotlib.colors
import matplotlib.pyplot as plt
import numpy as np
from PyQt6 import QtCore, QtGui, QtWidgets

from frheed.ui import common

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


def is_reversed_colormap(cmap: str | Colormap) -> bool:
    """Returns whether or not a colormap name is the reversed version of a colormap.

    Reversed colormap names end with "_r" - see the matplotlib documentation for details.

    https://matplotlib.org/stable/gallery/color/colormap_reference.html#reversed-colormaps
    """
    cmap = cmap if isinstance(cmap, str) else cmap.name
    return cmap.endswith("_r")


def get_reversed_colormap_name(cmap: str | Colormap) -> str:
    """Returns the name for the reversed version of a colormap.

    This is done by appending "_r" to the colormap name if it does not already end with "_r".

    https://matplotlib.org/stable/gallery/color/colormap_reference.html#reversed-colormaps
    """
    # Any matplotlib colormap can be reversed by appending "_r" to its name
    cmap = cmap if isinstance(cmap, str) else cmap.name
    return cmap if is_reversed_colormap(cmap) else f"{cmap}_r"


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
        cmap: Colormap | str | None,
        width: int = 128,
        height: int = 128,
    ) -> None:
        if cmap == "":
            cmap = None
        elif isinstance(cmap, str):
            cmap = plt.get_cmap(cmap, lut=width)

        self._cmap = cmap

        # Get RGBA data for the colormap
        if cmap is None:
            # Use transparent image if there is no colormap
            rgba = np.full((height, width, 4), fill_value=(0, 0, 0, 0))
        else:
            # Generate a gradient image that uses the full colormap
            row = np.linspace(0, 1, width)
            rgba = plt.cm.ScalarMappable(cmap=cmap).to_rgba(np.tile(row, (height, 1)), bytes=True)

        # Initialize the image using the colormap data
        bytes_per_line = rgba.strides[0]
        image_format = QtGui.QImage.Format.Format_RGBA8888
        super().__init__(rgba.data, width, height, bytes_per_line, image_format)

    def get_colormap(self) -> Colormap | None:
        """Returns the colormap the image represents."""
        return self._cmap

    def get_colormap_name(self) -> str | None:
        """Returns the name of the colormap the image represents."""
        return self._cmap.name if self._cmap is not None else None

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


class ColormapSelectionAction(QtGui.QAction):
    """An action used to select a colormap."""

    def __init__(
        self,
        cmap: Colormap | str | None,
        group: QtGui.QActionGroup,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        cmap_image = ColormapImage(cmap)
        cmap_name = cmap_image.get_colormap_name()
        if not cmap:
            super().__init__("No colormap", parent)
        else:
            super().__init__(cmap_image.to_icon(), cmap_name, parent)

        # All colormap actions should be checkable and belong to an action group
        self.setCheckable(True)
        self.setActionGroup(group)

        # Make the action font bold when checked and normal when not checked since the icon can
        # make it difficult to see the default light blue box indicator that the item is selected
        self.toggled.connect(self.on_toggled)

        # Store the colormap name as item data for passing around via signals and slots
        self._cmap_name = cmap_name
        self.setData(cmap_name)

        # Show a 256x32 image of the colormap as its tooltip
        # https://stackoverflow.com/a/34300771/10342097
        # TODO(ecyoung3): There is still a slight margin on the tooltip - consider creating a
        #   custom widget instead and intercepting the ToolTip event.
        if cmap is not None:
            image_data = QtCore.QByteArray()
            image_buffer = QtCore.QBuffer(image_data)
            cmap_image.scaled(256, 32).save(image_buffer, "PNG", 100)
            image_data_base64 = image_data.toBase64().data().decode()
            tooltip = f"<img src='data:image/png;base64, {image_data_base64}'>"
            self.setToolTip(tooltip)

    @QtCore.pyqtSlot(bool)
    def on_toggled(self, checked: bool) -> None:
        """Updates the action font when it is toggled for any reason."""
        if checked:
            logging.info("Selected colormap %r", self.get_colormap_name())

        font = self.font()
        font.setBold(checked)
        self.setFont(font)

        # Also make the parent menu font bold to indicate it contains the selected item
        # NOTE: This works even if the previously-checked action was in the same menu because the
        #   checked action triggers second (bold -> normal -> bold)
        for obj in self.associatedObjects():
            if isinstance(obj, QtWidgets.QMenu):
                if (menu_action := obj.menuAction()) is not None:
                    menu_font = menu_action.font()
                    menu_font.setBold(checked)
                    menu_action.setFont(menu_font)

    def get_colormap_name(self) -> str | None:
        """Returns the name of the colormap associated with this action."""
        return self._cmap_name


class ColormapSelectionMenu(QtWidgets.QMenu):
    """A menu of available colormaps."""

    # Signal emitted when a colormap is selected
    colormap_selected = QtCore.pyqtSignal(str)

    def __init__(
        self,
        title: str,
        colormaps: Sequence[str | Colormap | ColormapFamily],
        include_none_selected: bool = True,
        include_reversed: bool = True,
        action_group: QtGui.QActionGroup | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        """Initializes the colormap menu.

        Args:
            title: The text to display for the menu.
            colormaps: The colormaps and/or colormap families to include in the menu. Colormap
                families will be added as sub-menus containing all colormaps in that family.
            include_none_selected: Whether to include an item at the top of the menu to represent
                that no colormap is selected.
            include_reversed: Whether to include reversed versions of all colormaps in the menu.
            action_group: The action group to add all colormap actions to, or `None` if an action
                group should be created automatically.
            parent: The widget to set as the parent of the menu.
        """
        super().__init__(title, parent)

        # Create an action group if necessary and make sure it's exclusive so that at most one
        # choice can be selected at a time
        if action_group is None:
            action_group = QtGui.QActionGroup(self)

        action_group.setExclusive(True)
        self._action_group = action_group

        # Create the item that represents no colormap being selected
        if include_none_selected:
            none_action = ColormapSelectionAction(None, action_group, self)
            self.addAction(none_action)

            # If the "None" action is included, select it by default
            none_action.setChecked(True)

        # Add actions for each of the colormaps to the menu and to the action group if necessary
        for cmap in colormaps:
            if isinstance(cmap, ColormapFamily):
                # Create a sub-menu for the colormap family but _without_ the "None" item, which
                # should only be created for top-level colormap menus
                submenu = ColormapSelectionMenu.for_family(
                    cmap,
                    include_none_selected=False,
                    include_reversed=include_reversed,
                    action_group=action_group,
                    parent=self,
                )
                submenu_action = self.addMenu(submenu)

                # Make the sub-menu checkable to indicate if it contains the selected colormap
                if submenu_action is not None:
                    submenu_action.setCheckable(True)

                # Disconnect the triggered signal, otherwise it will fire twice (once for the parent
                # menu connection and once for the child menu connection)
                # submenu.triggered.disconnect()
            else:
                # Create an action for the colormap and optionally its reversed version
                self.addAction(ColormapSelectionAction(cmap, action_group, self))
                if include_reversed and not is_reversed_colormap(cmap):
                    reversed_cmap_name = get_reversed_colormap_name(cmap)
                    self.addAction(ColormapSelectionAction(reversed_cmap_name, action_group, self))

        # Enable tooltips so the user can preview the colormap when hovering over it
        self.setToolTipsVisible(True)

        # Emit the `colormap_changed` signal when a colormap action is clicked
        self.triggered.connect(self.on_action_triggered)

    @classmethod
    def for_family(
        cls,
        family: ColormapFamily,
        include_none_selected: bool = True,
        include_reversed: bool = True,
        action_group: QtGui.QActionGroup | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> ColormapSelectionMenu:
        """Returns a colormap menu containing colormaps in the given family."""
        # Generate the menu title based on the family name, e.g. "SEQUENTIAL_2" -> "Sequential (2)"
        title_parts = family.name.split("_")
        title = " ".join(f"({part})" if part.isnumeric() else part.title() for part in title_parts)
        cmap_names = family.value
        return cls(title, cmap_names, include_none_selected, include_reversed, action_group, parent)

    @classmethod
    def for_all_colormaps(
        cls, title: str = "&Colormaps", parent: QtWidgets.QWidget | None = None
    ) -> ColormapSelectionMenu:
        """Returns a colormap menu containing submenus for all colormaps in all families."""
        return cls(title, list(ColormapFamily), include_reversed=True, parent=parent)

    @QtCore.pyqtSlot(QtGui.QAction)
    def on_action_triggered(self, action: QtGui.QAction) -> None:
        """Emits the colormap name associated with the triggered action."""
        if isinstance(action, ColormapSelectionAction):
            self.colormap_selected.emit(action.get_colormap_name())

    def set_selected_colormap(self, cmap: str | None) -> None:
        """Sets the selected colormap.

        This method should be used if setting the colormap programmatically, otherwise the
        `colormap_changed` signal will not be emitted.
        """
        if cmap == self.get_selected_colormap():
            logging.info("Colormap %r is already selected", cmap)
            return

        for action in self._action_group.actions():
            if isinstance(action, ColormapSelectionAction) and action.get_colormap_name() == cmap:
                action.setChecked(True)
                self.colormap_selected.emit(cmap)
                break
        else:
            logging.warning("Colormap %r not found in menu")

    def get_selected_colormap(self) -> str | None:
        """Returns the name of the currently-selected colormap."""
        if (action := self._action_group.checkedAction()) is None:
            # No action selected
            return None
        elif not isinstance(action, ColormapSelectionAction):
            # Action is selected, but it's the "None" action representing no colormap selection
            return None
        else:
            # A colormap is selected
            return action.get_colormap_name()


class ColormapSelectionToolButton(common.MenuButton):
    """A button that opens a colormap selection menu and displays the selected colormap."""

    def __init__(
        self, menu: ColormapSelectionMenu | None = None, parent: QtWidgets.QWidget | None = None
    ) -> None:
        # If no menu is provided, initialize using a menu containing all colormaps
        if menu is None:
            menu = ColormapSelectionMenu.for_all_colormaps()

        super().__init__(menu, parent=parent)

        # Indicate that the button is for selecting the colormap when hovering it with the mouse
        self.setToolTip("Colormap")

        # Update the button icon and text now and whenever another colormap is selected
        self.on_colormap_selected(menu.get_selected_colormap())
        self.colormap_selected.connect(self.on_colormap_selected)

    @property
    def colormap_selected(self) -> QtCore.pyqtBoundSignal:
        """The signal emitted when a colormap is selected."""
        if isinstance((menu := self.menu()), ColormapSelectionMenu):
            return menu.colormap_selected

        raise NotImplementedError(f"Menu {menu!r} does not implement a `colormap_selected` signal")

    @QtCore.pyqtSlot(str)
    def on_colormap_selected(self, cmap: str | None) -> None:
        """Updates the action icon and text when a colormap is selected."""
        if cmap:
            # Show the icon and text
            icon = ColormapImage(cmap).to_icon()
            text = cmap
        else:
            # Hide the icon if no colormap is selected and only show text
            icon = QtGui.QIcon()
            text = "No colormap"

        # Set the icon _before_ the text, because eliding relies on knowing the icon width
        self.setIcon(icon)
        self.set_text(text)
