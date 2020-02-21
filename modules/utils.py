# -*- coding: utf-8 -*-
"""FRHEED

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

"""

# =============================================================================
#
# This module is used to set or change the base directory for FRHEED.
#
# =============================================================================

import os
import sys
import configparser
import pathvalidate
import threading
from PyQt5 import QtWidgets, QtGui, QtCore
import pyqtgraph as pg
from pyqtgraph import PlotWidget

from . import utils

def getConfig(configname: str = 'config.ini'):
    working_dir = os.getcwd() # get the current working directory that this script is running from
    config_path = os.path.join(working_dir, configname)
    if not os.path.exists(config_path):
        config_default = """
[Default]
camera_type = 
path = 
colormap = gist_gray
user = 
sample = 
flir_gamma = 0.6
flir_blacklevel = 0.0
flir_gain = 25.0
flir_exposure = 3500
usb_exposure = -4

[Profile 1]
profile_name = Profile 1
colormap = gist_gray
inverted = False
usb_exposure = -4
flir_exposure = 5000
flir_gamma = 0.6
flir_blacklevel = 0.0
flir_gain = 25.0

[Profile 2]
profile_name = Profile 2
colormap = gist_gray
inverted = False
usb_exposure = -4
flir_exposure = 5000
flir_gamma = 0.6
flir_blacklevel = 0.0
flir_gain = 25.0

[Profile 3]
profile_name = Profile 3
colormap = gist_gray
inverted = False
usb_exposure = -4
flir_exposure = 5000
flir_gamma = 0.6
flir_blacklevel = 0.0
flir_gain = 25.0
"""
        with open(config_path, 'x') as c:
            c.write(config_default)
    config = configparser.ConfigParser()
    config.read(config_path)
    return config_path, config

def setBasepath(parent, change: bool = False):
    parent = parent
    parent.basepath = parent.config['Default']['path']
    user = parent.config['Default']['user']
    sample = parent.config['Default']['sample']
    if not os.path.exists(parent.basepath) or change:
        QtWidgets.QMessageBox.warning(parent, 'Notice', 
            'Please select a base directory for saving files.')
        parent.basepath = QtWidgets.QFileDialog.getExistingDirectory(None,
                                                       'Select Base Directory')
        if parent.basepath != '':
            parent.config['Default']['path'] = parent.basepath
            with open(parent.configfile, 'w') as cfg:
                parent.config.write(cfg)
        else:
            parent.close()
            parent.app.quit()
            sys.exit()
    # Set base path to config
    userpath = os.path.join(parent.basepath, user, '')
    samplepath = os.path.join(userpath, sample, '')
    if not os.path.exists(userpath) or user == '':
        setUser(parent, False)
    if not os.path.exists(samplepath) or sample == '':
        setSample(parent)
    with open(parent.configfile, 'w') as cfg:
        parent.config.write(cfg)
        print('Config file path locations updated.')

def setUser(parent, changesample: bool = True):
    # Make sure the base path exists and set it if it doesn't
    if not os.path.exists(parent.basepath):
        parent.basepath = setBasepath(parent)
        
    # Prompt user to enter a username
    entry, accepted = QtWidgets.QInputDialog().getText(
                            parent, 
                            'Change User', 
                            'Enter user name:')
    
    # Make sure the chosen username is valid
    testpath = os.path.join(parent.basepath, entry, '')
    if accepted and entry != '' and pathvalidate.is_valid_filepath(
                                        testpath, 
                                        platform='Windows'):
        userpath = testpath
        parent.user = entry

    # If the username is invalid, retry creation
    elif accepted and not pathvalidate.is_valid_filepath(
                                testpath,
                                platform='Windows'):
        QtWidgets.QMessageBox.warning(parent, 
              'Alert', 
              'User name contains invalid characters for folder creation.')
        setUser(parent, False)
        
    # If no username is entered, exit prematurely
    elif entry == '':
        setUser(parent, False)
    
    userpath = os.path.join(parent.basepath, parent.user, '')
    if not os.path.exists(userpath):
        os.makedirs(userpath)
        
    # Update parent variables
    parent.user = entry
    
    # Update user label text
    parent.userLabel.setText(entry)
    
    # Update the config file
    parent.config['Default']['user'] = entry
    with open(parent.configfile, 'w') as cfg:
        parent.config.write(cfg)
        
    # Run the sample entry dialog if changing samples
    if changesample:
        setSample(parent)
    else:
        samplepath = os.path.join(parent.basepath, parent.user, parent.user, '')
        if not os.path.exists(samplepath) and pathvalidate.is_valid_filepath(
                                                testpath, 
                                                platform='Windows'):
            os.makedirs(samplepath)
            
def setSample(parent):
    # Make sure basepath is valid and exists
    if not os.path.exists(parent.basepath) or not pathvalidate.is_valid_filepath(
                                                      parent.basepath,
                                                      platform='Windows'):
        setBasepath(parent)
        
    # Make sure userpath is valid and exists
    userpath = os.path.join(parent.basepath, parent.user, '')
    if not os.path.exists(userpath) or not pathvalidate.is_valid_filepath(
                                                      userpath,
                                                      platform='Windows'):
        setUser(parent, False)
        
    # Prompt user to enter sample name
    entry, accepted = QtWidgets.QInputDialog().getText(
        parent, 
        'Change Sample', 
        'Enter sample name:')
    testpath = os.path.join(userpath, entry, '')
    if accepted and entry != '' and pathvalidate.is_valid_filepath(
                                        testpath, 
                                        platform='Windows'):
        samplepath = testpath
    elif accepted:
        QtWidgets.QMessageBox.warning(
            parent, 
            'Alert', 
            'Sample name contains invalid characters for folder creation.')
        setSample(parent)
        
    elif not accepted and os.path.exists(os.path.join(userpath, 
                                                          parent.sample)):
        return
    elif not accepted:
        setSample(parent)
    else:
        return
            
    # Make the sample directory if it's valid and doesn't already exist
    if not os.path.exists(testpath) and pathvalidate.is_valid_filepath(
                                            testpath,
                                            platform='Windows'):
        os.makedirs(testpath)
        
    # Update the parent variable
    parent.sample = entry
        
    # Update the sample label text
    parent.sampleLabel.setText(entry)
    
    # Update the config file
    parent.config['Default']['sample'] = parent.sample
    with open(parent.configfile, 'w') as cfg:
        parent.config.write(cfg)
        
# Open the current save directory
def openDirectory():
    configfile, config = utils.getConfig()
    base = config['Default']['path']
    user = config['Default']['user']
    sample = config['Default']['sample']
    path = os.path.join(base, user, sample, '')
    p = os.path.realpath(path)
    os.startfile(p)  # startfile only works on Windows

def addPlotTab(tabwidget, *args, **kwargs):
    tabnum = tabwidget.count() + 1
    tabwidget.setTabsClosable(True)
    tabwidget.setMovable(True)
    tabwidget.setTabBarAutoHide(False)
    newtab = QtWidgets.QWidget()
    # newtab.setObjectName("tab")
    layout = QtWidgets.QGridLayout(newtab)
    # layout.setObjectName("gridLayout_20")
    axes = PlotWidget(newtab)
    sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, 
                                       QtWidgets.QSizePolicy.MinimumExpanding)
    sizePolicy.setHeightForWidth(axes.sizePolicy().hasHeightForWidth())
    axes.setSizePolicy(sizePolicy)
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
    axes.setPalette(palette)
    axes.setStyleSheet('')
    axes.setFrameShape(QtWidgets.QFrame.NoFrame)
    axes_name = f'StoredDataAxes{tabwidget.indexOf(newtab)}'
    axes.setObjectName(axes_name)
    layout.addWidget(axes, 0, 0, 1, 1)
    tabwidget.addTab(newtab, '')
    tabnum_txt = str(tabnum).zfill(2)
    tabtext = f'Data {tabnum_txt}'
    tabwidget.setTabText(tabwidget.indexOf(newtab), tabtext)
    return axes

def addPlots(axes: object, *args, **kwargs) -> dict:
    plots = {
        'red':      axes.plot(
                        pen = pg.mkPen((228, 88, 101), width=1), 
                        clear = True), 
        'green':    axes.plot(
                        pen = pg.mkPen((155, 229, 100), width=1), 
                        clear = False), 
        'blue':     axes.plot(
                        pen = pg.mkPen((0, 167, 209), width=1), 
                        clear = False),
        'orange':   axes.plot(
                        pen = pg.mkPen((244, 187, 71), width=1), 
                        clear = False), 
        'purple':   axes.plot(
                        pen = pg.mkPen((125, 43, 155), width=1), 
                        clear = False),
        }
    return plots

def formatPlots(plotwidget, style: str = 'area'):
    plotfont = QtGui.QFont('Bahnschrift')
    fontstyle = {
        'color': 'white', 
        'font-size': '11pt', 
        'font-family': 'Bahnschrift SemiLight'}
    tickstyle = {'tickTextOffset': 10}
    plotfont.setPixelSize(12)
    plotwidget.plotItem.showGrid(True, False)
    plotwidget.plotItem.getAxis('bottom').tickFont = plotfont
    plotwidget.plotItem.getAxis('bottom').setStyle(**tickstyle)
    plotwidget.setContentsMargins(0, 4, 10, 0)
    for axis in ['right', 'top']:
        plotwidget.plotItem.getAxis(axis).show()
        if axis != 'top':
            plotwidget.plotItem.getAxis(axis).setWidth(6)
        else:
            plotwidget.plotItem.getAxis(axis).setHeight(6)
        plotwidget.plotItem.getAxis(axis).setStyle(tickTextOffset = 30)
    if style == 'area':
        plotwidget.setLimits(xMin=0)
        plotwidget.setLabel('bottom', 'Time (s)', **fontstyle)
        plotwidget.setLabel('left', 'Intensity (Counts/Pixel)', **fontstyle)
        plotwidget.plotItem.getAxis('bottom').setHeight(42)
        plotwidget.plotItem.getAxis('left').setWidth(48)

# =============================================================================
# GRAVEYARD
# =============================================================================

# def makeThread(func, args):
#     p = threading.Thread(target=func, args=args)  # again, fps isn't actually used but leave it
#     return p

# def convertExposure(level: int):
#     lvl = str(level)
#     # USB exposure level on the left, estimated exposure time on the right (in ms)
#     # Source: http://www.principiaprogramatica.com/2017/06/11/setting-manual-exposure-in-opencv/
#     realtimes = {
#         '-1':   640,
#         '-2':   320,
#         '-3':   160,
#         '-4':   80,
#         '-5':   40,
#         '-6':   20,
#         '-7':   10,
#         '-8':   5,
#         '-9':   2.5,
#         '-10':  1.25,
#         '-11':  0.650,
#         '-12':  0.312,
#         '-13':  0.150,
#         }
#     if lvl in realtimes.keys():
#         exptime = realtimes[lvl]
        
#     else:
#         exptime = lvl
        
#     return exptime