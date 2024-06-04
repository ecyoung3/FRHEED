"""Common UI components used in multiple other modules."""

from PyQt6 import QtCore, QtGui, QtWidgets


class MenuButton(QtWidgets.QPushButton):
    """A fixed-size button that pops up a menu below it when clicked."""

    def __init__(
        self,
        menu: QtWidgets.QMenu,
        w: int = 100,
        h: int = 32,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        # Setting a fixed size ensures that other items in the toolbar won't shift due to this
        # button resizing due to its text or icon changing
        self.setFixedSize(QtCore.QSize(w, h))

        # Align the text and icon to the left
        self.setStyleSheet("text-align: left;")

        # Don't accept any focus
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)

        # Setting the menu causes (a) a down arrow to show on the right of the button and (b) a bug
        # where the "clicked" style never goes away after opening the menu once, so instead manually
        # manage the state/menu.
        self._menu = menu
        self.clicked.connect(self.show_menu)
        menu.aboutToHide.connect(self.on_menu_hidden)

    @QtCore.pyqtSlot()
    def on_menu_hidden(self) -> None:
        self.setDown(False)

    def menu(self) -> QtWidgets.QMenu | None:
        return self._menu

    def show_menu(self) -> None:
        """Show the menu at the bottom left corner of the button."""
        self._menu.popup(self.mapToGlobal(self.rect().bottomLeft()))
        self.setDown(True)

    def set_text(self, text: str | None) -> None:
        """Sets text, eliding to the right if necessary."""
        if not text:
            self.setText(None)
            return

        # Add space between the text and border if there is no icon
        # NOTE: We have to do this because setting the left margin seems bugged and has no effect.
        if self.icon().isNull():
            text = f" {text}"

        # Calculate the available space for drawing text
        # TODO(ecyoung3): This is not always reliable - sometimes the text is still too long and is
        #   elided in the middle in addition to the right, which looks very strange.
        margins = self.contentsMargins()
        width = self.width() - margins.left() - margins.right() - 10

        # Account for the icon width if it's visible
        if not self.icon().isNull():
            width -= self.iconSize().width()

        # Add spacing between the icon and colormap and show "..." if the text is too long
        font_metrics = QtGui.QFontMetrics(self.font())
        elided_text = font_metrics.elidedText(text, QtCore.Qt.TextElideMode.ElideRight, width)
        self.setText(elided_text)
