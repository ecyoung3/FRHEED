# -*- coding: utf-8 -*-
'''
FRHEED

This is a real-time RHEED (Reflection High Energy Electron Diffraction)
analysis program designed for use with USB or FLIR GigE cameras.

Author: Elliot Young
        elliot.young1996@gmail.com
        
    Formerly:
        Materials Department
        University of California, Santa Barbara
        Chris Palmstrøm Research Group
        ecyoung@ucsb.edu

Originally created October 2018.

Github: https://github.com/ecyoung3/FRHEED

'''

from PyQt5 import QtWidgets, QtGui, QtCore
from pyqtgraph import PlotWidget

from . import guifuncs

def addPlotTab(self, tabwidget, *args, **kwargs):
    '''
    EDIT TAB WIDGET PROPERTIES
    '''
    tabwidget.setTabsClosable(True)
    tabwidget.setMovable(True)
    tabwidget.setTabBarAutoHide(False)
    
    tabnum = tabwidget.count() + 1
    
    ''' 
    CREATE THE NEW TAB
    '''    
    newtab = QtWidgets.QWidget()
    tabname = f'StoredDataTab{tabnum}'
    
    '''
    CREATE THE LAYOUTS
    '''
    layout = QtWidgets.QGridLayout(newtab)
    layout.setContentsMargins(4, 6, 4, 4)
    layout.setHorizontalSpacing(6)
    layout.setVerticalSpacing(0)
    
    topleftlayout = QtWidgets.QGridLayout(newtab)
    topleftlayout.setContentsMargins(0, 0, -1, -1)
    topleftlayout.setSpacing(0)
    
    topcenterlayout = QtWidgets.QGridLayout()
    
    toprightlayout = QtWidgets.QGridLayout()
    toprightlayout.setContentsMargins(-1, 0, -1, -1)
    toprightlayout.setSpacing(0)
    
    '''
    ADDING THE FREQUENCY LABEL
    '''
    freqlabel = QtWidgets.QLabel(newtab)
    sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, 
                                       QtWidgets.QSizePolicy.Preferred)
    sizePolicy.setHorizontalStretch(0)
    sizePolicy.setVerticalStretch(0)
    sizePolicy.setHeightForWidth(freqlabel.sizePolicy().hasHeightForWidth())
    freqlabel.setSizePolicy(sizePolicy)
    freqlabel.setPalette(standardPalette())
    freqlabel.setMouseTracking(True)
    freqlabel.setText('')
    freqlabel.setMinimumSize(QtCore.QSize(90, 0))
    freqlabelname = f'{tabname}FreqLabel'
    freqlabel.setObjectName(freqlabelname)
    freqlabel.setAlignment(QtCore.Qt.AlignCenter)
    freqlabel.setIndent(6)
    topleftlayout.addWidget(freqlabel, 0, 0, 1, 1)
    layout.addLayout(topleftlayout, 0, 0, 1, 1)    
    
    '''
    ADDING THE NUMBER OF PEAKS LABEL
    '''
    numpeakslabel = QtWidgets.QLabel(newtab)
    sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Maximum, 
                                       QtWidgets.QSizePolicy.Preferred)
    sizePolicy.setHorizontalStretch(0)
    sizePolicy.setVerticalStretch(0)
    sizePolicy.setHeightForWidth(numpeakslabel.sizePolicy().hasHeightForWidth())
    numpeakslabel.setSizePolicy(sizePolicy)
    numpeakslabel.setMaximumSize(QtCore.QSize(60, 16777215))
    numpeakslabel.setPalette(standardPalette())
    font = QtGui.QFont()
    font.setFamily("Bahnschrift SemiLight")
    font.setPointSize(11)
    font.setBold(False)
    font.setItalic(False)
    font.setWeight(50)
    numpeakslabel.setFont(font)
    numpeakslabel.setText('Peaks:')
    numpeakslabel.setMouseTracking(True)
    numpeakslabel.setAlignment(QtCore.Qt.AlignCenter)
    numpeakslabel.setIndent(0)
    numpeakslabel.setObjectName("numpeaks1Label")
    topcenterlayout.addWidget(numpeakslabel, 0, 0, 1, 1)

    '''
    SET UP THE SPINBOX FOR NUMBER OF PEAKS
    '''
    numpeaks = QtWidgets.QSpinBox(newtab)
    sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Maximum, 
                                       QtWidgets.QSizePolicy.Fixed)
    sizePolicy.setHorizontalStretch(0)
    sizePolicy.setVerticalStretch(0)
    sizePolicy.setHeightForWidth(numpeaks.sizePolicy().hasHeightForWidth())
    numpeaks.setSizePolicy(sizePolicy)
    numpeaks.setMaximumSize(QtCore.QSize(16777215, 16777215))
    numpeaks.setPalette(spinboxPalette())
    font = QtGui.QFont()
    font.setFamily('Bahnschrift SemiLight')
    font.setPointSize(11)
    font.setBold(False)
    font.setItalic(False)
    font.setWeight(50)
    numpeaks.setFont(font)
    numpeaks.setMouseTracking(True)
    numpeaks.setWrapping(False)
    numpeaks.setFrame(True)
    numpeaks.setAlignment(QtCore.Qt.AlignCenter)
    numpeaks.setButtonSymbols(QtWidgets.QAbstractSpinBox.UpDownArrows)
    numpeaks.setKeyboardTracking(False)
    numpeaks.setMinimum(1)
    numpeaks.setMaximum(99)
    numpeaks.setProperty('value', 10)
    numpeaksname = f'{tabname}NumPeaks'
    numpeaks.setObjectName(numpeaksname)
    topcenterlayout.addWidget(numpeaks, 0, 1, 1, 1)
    layout.addLayout(topcenterlayout, 0, 1, 1, 1)
    
    # Connect the spinbox the the manual frequency calculation function
    numpeaks.valueChanged.connect(lambda: guifuncs.manualFreqCalc(self,
                                                                  axes))
    
    '''
    ADDING THE T = LABEL
    '''
    tequals = QtWidgets.QLabel(newtab)
    sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, 
                                       QtWidgets.QSizePolicy.Preferred)
    sizePolicy.setHorizontalStretch(0)
    sizePolicy.setVerticalStretch(0)
    sizePolicy.setHeightForWidth(tequals.sizePolicy().hasHeightForWidth())
    tequals.setSizePolicy(sizePolicy)
    tequals.setMinimumSize(QtCore.QSize(45, 0))
    tequals.setText('')
    tequalsname = f'{tabname}TEqualsLabel'
    tequals.setObjectName(tequalsname)
    tequals.setAlignment(QtCore.Qt.AlignRight|
                         QtCore.Qt.AlignTrailing|
                         QtCore.Qt.AlignVCenter)
    toprightlayout.addWidget(tequals, 0, 0, 1, 1)
    layout.addLayout(toprightlayout, 0, 2, 1, 1)
    
    '''
    LABEL TO DISPLAY CURSOR POSITION
    '''
    tlabel = QtWidgets.QLabel(newtab)
    sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, 
                                       QtWidgets.QSizePolicy.Preferred)
    sizePolicy.setHorizontalStretch(0)
    sizePolicy.setVerticalStretch(0)
    sizePolicy.setHeightForWidth(tlabel.sizePolicy().hasHeightForWidth())
    tlabel.setSizePolicy(sizePolicy)
    tlabel.setMinimumSize(QtCore.QSize(45, 0))
    tlabel.setPalette(standardPalette())
    tlabel.setMouseTracking(True)
    tlabel.setText('')
    tlabelname = f'{tabname}TLabel'
    tlabel.setObjectName(tlabelname)
    tlabel.setAlignment(QtCore.Qt.AlignLeading|
                        QtCore.Qt.AlignLeft|
                        QtCore.Qt.AlignVCenter)
    tlabel.setIndent(-1)
    toprightlayout.addWidget(tlabel, 0, 1, 1, 1)
    
    '''
    ADDING THE PLOT WIDGET
    '''
    axes = PlotWidget(newtab)
    sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, 
                                        QtWidgets.QSizePolicy.MinimumExpanding)
    sizePolicy.setHeightForWidth(axes.sizePolicy().hasHeightForWidth())
    axes.setSizePolicy(sizePolicy)
    axes.setPalette(standardPalette())
    axes.setFrameShape(QtWidgets.QFrame.NoFrame)
    axes.setMouseTracking(True)
    axes_name = f'{tabname}Axes'
    axes.setObjectName(axes_name)
    tabwidget.addTab(newtab, '')
    tabnum_txt = str(tabnum).zfill(2)
    tabtext = f'Data {tabnum_txt}'
    tabwidget.setTabText(tabwidget.indexOf(newtab), tabtext)
    axes.setPalette(standardPalette())
    layout.addWidget(axes, 1, 0, 1, 3)
    
    return axes

# =============================================================================
# COLOR PALETTES FOR WIDGETS
# =============================================================================

def standardPalette():
    palette = QtGui.QPalette()
    brush = QtGui.QBrush(QtGui.QColor(255, 255, 255))
    brush.setStyle(QtCore.Qt.SolidPattern)
    palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.WindowText, brush)
    brush = QtGui.QBrush(QtGui.QColor(25, 35, 45))
    brush.setStyle(QtCore.Qt.SolidPattern)
    palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.Button, brush)
    brush = QtGui.QBrush(QtGui.QColor(255, 255, 255))
    brush.setStyle(QtCore.Qt.SolidPattern)
    palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.Text, brush)
    brush = QtGui.QBrush(QtGui.QColor(255, 255, 255))
    brush.setStyle(QtCore.Qt.SolidPattern)
    palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.ButtonText, brush)
    brush = QtGui.QBrush(QtGui.QColor(25, 35, 45))
    brush.setStyle(QtCore.Qt.SolidPattern)
    palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.Base, brush)
    brush = QtGui.QBrush(QtGui.QColor(25, 35, 45))
    brush.setStyle(QtCore.Qt.SolidPattern)
    palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.Window, brush)
    brush = QtGui.QBrush(QtGui.QColor(255, 255, 255))
    brush.setStyle(QtCore.Qt.SolidPattern)
    palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.WindowText, brush)
    brush = QtGui.QBrush(QtGui.QColor(25, 35, 45))
    brush.setStyle(QtCore.Qt.SolidPattern)
    palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.Button, brush)
    brush = QtGui.QBrush(QtGui.QColor(255, 255, 255))
    brush.setStyle(QtCore.Qt.SolidPattern)
    palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.Text, brush)
    brush = QtGui.QBrush(QtGui.QColor(255, 255, 255))
    brush.setStyle(QtCore.Qt.SolidPattern)
    palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.ButtonText, brush)
    brush = QtGui.QBrush(QtGui.QColor(25, 35, 45))
    brush.setStyle(QtCore.Qt.SolidPattern)
    palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.Base, brush)
    brush = QtGui.QBrush(QtGui.QColor(25, 35, 45))
    brush.setStyle(QtCore.Qt.SolidPattern)
    palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.Window, brush)
    brush = QtGui.QBrush(QtGui.QColor(255, 255, 255))
    brush.setStyle(QtCore.Qt.SolidPattern)
    palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.WindowText, brush)
    brush = QtGui.QBrush(QtGui.QColor(25, 35, 45))
    brush.setStyle(QtCore.Qt.SolidPattern)
    palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.Button, brush)
    brush = QtGui.QBrush(QtGui.QColor(255, 255, 255))
    brush.setStyle(QtCore.Qt.SolidPattern)
    palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.Text, brush)
    brush = QtGui.QBrush(QtGui.QColor(255, 255, 255))
    brush.setStyle(QtCore.Qt.SolidPattern)
    palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.ButtonText, brush)
    brush = QtGui.QBrush(QtGui.QColor(25, 35, 45))
    brush.setStyle(QtCore.Qt.SolidPattern)
    palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.Base, brush)
    brush = QtGui.QBrush(QtGui.QColor(25, 35, 45))
    brush.setStyle(QtCore.Qt.SolidPattern)
    palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.Window, brush)
    
    return palette

def spinboxPalette():
    palette = QtGui.QPalette()
    brush = QtGui.QBrush(QtGui.QColor(155, 229, 100))
    brush.setStyle(QtCore.Qt.SolidPattern)
    palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.WindowText, brush)
    gradient = QtGui.QLinearGradient(0.5, 1.0, 0.5, 0.0)
    gradient.setSpread(QtGui.QGradient.PadSpread)
    gradient.setCoordinateMode(QtGui.QGradient.ObjectBoundingMode)
    gradient.setColorAt(0.0, QtGui.QColor(44, 55, 64))
    gradient.setColorAt(1.0, QtGui.QColor(68, 86, 100, 235))
    brush = QtGui.QBrush(gradient)
    palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.Button, brush)
    brush = QtGui.QBrush(QtGui.QColor(155, 229, 100))
    brush.setStyle(QtCore.Qt.SolidPattern)
    palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.Text, brush)
    brush = QtGui.QBrush(QtGui.QColor(155, 229, 100))
    brush.setStyle(QtCore.Qt.SolidPattern)
    palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.ButtonText, brush)
    brush = QtGui.QBrush(QtGui.QColor(0, 0, 0))
    brush.setStyle(QtCore.Qt.NoBrush)
    palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.Base, brush)
    gradient = QtGui.QLinearGradient(0.5, 1.0, 0.5, 0.0)
    gradient.setSpread(QtGui.QGradient.PadSpread)
    gradient.setCoordinateMode(QtGui.QGradient.ObjectBoundingMode)
    gradient.setColorAt(0.0, QtGui.QColor(44, 55, 64))
    gradient.setColorAt(1.0, QtGui.QColor(68, 86, 100, 235))
    brush = QtGui.QBrush(gradient)
    palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.Window, brush)
    brush = QtGui.QBrush(QtGui.QColor(155, 229, 100))
    brush.setStyle(QtCore.Qt.SolidPattern)
    palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.WindowText, brush)
    gradient = QtGui.QLinearGradient(0.5, 1.0, 0.5, 0.0)
    gradient.setSpread(QtGui.QGradient.PadSpread)
    gradient.setCoordinateMode(QtGui.QGradient.ObjectBoundingMode)
    gradient.setColorAt(0.0, QtGui.QColor(44, 55, 64))
    gradient.setColorAt(1.0, QtGui.QColor(68, 86, 100, 235))
    brush = QtGui.QBrush(gradient)
    palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.Button, brush)
    brush = QtGui.QBrush(QtGui.QColor(155, 229, 100))
    brush.setStyle(QtCore.Qt.SolidPattern)
    palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.Text, brush)
    brush = QtGui.QBrush(QtGui.QColor(155, 229, 100))
    brush.setStyle(QtCore.Qt.SolidPattern)
    palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.ButtonText, brush)
    brush = QtGui.QBrush(QtGui.QColor(0, 0, 0))
    brush.setStyle(QtCore.Qt.NoBrush)
    palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.Base, brush)
    gradient = QtGui.QLinearGradient(0.5, 1.0, 0.5, 0.0)
    gradient.setSpread(QtGui.QGradient.PadSpread)
    gradient.setCoordinateMode(QtGui.QGradient.ObjectBoundingMode)
    gradient.setColorAt(0.0, QtGui.QColor(44, 55, 64))
    gradient.setColorAt(1.0, QtGui.QColor(68, 86, 100, 235))
    brush = QtGui.QBrush(gradient)
    palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.Window, brush)
    brush = QtGui.QBrush(QtGui.QColor(155, 229, 100))
    brush.setStyle(QtCore.Qt.SolidPattern)
    palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.WindowText, brush)
    gradient = QtGui.QLinearGradient(0.5, 1.0, 0.5, 0.0)
    gradient.setSpread(QtGui.QGradient.PadSpread)
    gradient.setCoordinateMode(QtGui.QGradient.ObjectBoundingMode)
    gradient.setColorAt(0.0, QtGui.QColor(44, 55, 64))
    gradient.setColorAt(1.0, QtGui.QColor(68, 86, 100, 235))
    brush = QtGui.QBrush(gradient)
    palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.Button, brush)
    brush = QtGui.QBrush(QtGui.QColor(155, 229, 100))
    brush.setStyle(QtCore.Qt.SolidPattern)
    palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.Text, brush)
    brush = QtGui.QBrush(QtGui.QColor(155, 229, 100))
    brush.setStyle(QtCore.Qt.SolidPattern)
    palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.ButtonText, brush)
    brush = QtGui.QBrush(QtGui.QColor(0, 0, 0))
    brush.setStyle(QtCore.Qt.NoBrush)
    palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.Base, brush)
    gradient = QtGui.QLinearGradient(0.5, 1.0, 0.5, 0.0)
    gradient.setSpread(QtGui.QGradient.PadSpread)
    gradient.setCoordinateMode(QtGui.QGradient.ObjectBoundingMode)
    gradient.setColorAt(0.0, QtGui.QColor(44, 55, 64))
    gradient.setColorAt(1.0, QtGui.QColor(68, 86, 100, 235))
    brush = QtGui.QBrush(gradient)
    palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.Window, brush)
    
    return palette



