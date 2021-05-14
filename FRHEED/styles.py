# -*- coding: utf-8 -*-
"""
Styling for the PyQt5 interfaces and widgets.
"""

from dataclasses import dataclass

from PyQt5.QtGui import QPalette, QColor


@dataclass
class PaletteColor:
    role: str
    

class Palette:
    """ 
    A class to simplify easy QPalette creation
    https://doc.qt.io/qt-5/qpalette.html
    
    """
    
    