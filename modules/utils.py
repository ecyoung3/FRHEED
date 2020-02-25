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
import math
import numpy as np
from numpy.linalg import norm
import winsound
import time

from . import utils, guifuncs

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
        
    # If no username is entered, exit
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

def pythagDist(pt1, pt2):
    [x1, y1], [x2, y2] = [pt1[0], pt1[1]], [pt2[0], pt2[1]]
    dist = math.sqrt((x2-x1)**2 + (y2-y1)**2)
    return dist

def distFromSegment(point: list, segment: list) -> float:
    '''
    This determines if a point is within a certain distance of a line segment.
    Works only for segments that are either vertical or horizontal.
    '''
    # Points which define the line segment
    p1, p2 = segment[0], segment[1]
    x1, y1, x2, y2 = p1[0], p1[1], p2[0], p2[1]
    
    # Compute min/max values
    xmin, xmax = sorted([x1, x2])
    ymin, ymax = sorted([y1, y2])
    
    # The point of interest
    x, y = point[0], point[1]
    
    # Convert points to arrays so we can use the numpy library
    P1, P2 = np.asarray(p1), np.asarray(p2)
    pt = np.asarray(point)
    
    # Calculate the distance from the point in question to each endpoint
    dist1 = math.sqrt((x-x1)**2 + (y-y1)**2)
    dist2 = math.sqrt((x-x2)**2 + (y-y2)**2)
    
    # Determine if the point in question is inside or outisde of the endpoints
    if x1 == x2:
        between = ymin < y < ymax
    elif y1 == y2:
        between = xmin < x < xmax
    
    # Calculate the point's perpendicular distance from the line projection
    # if the point is between the segment endpoints
    if between:
        perpdist = norm(np.cross(P2-P1, P1-pt))/norm(P2-P1)
    else:
        perpdist = min(dist1, dist2)
    
    # Determine which of the computed distances is closest to get the answer
    dist = min(dist1, dist2, perpdist)
    
    return dist
    
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
    plotwidget.setXRange(0, 1, padding=0)
    plotwidget.plotItem.showGrid(True, False, 0.05)
    plotwidget.plotItem.getAxis('bottom').tickFont = plotfont
    plotwidget.plotItem.getAxis('bottom').setStyle(**tickstyle)
    plotwidget.setContentsMargins(0, 4, 10, 0)
    for axis in ['right', 'top', 'left']:
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
        plotwidget.plotItem.getAxis('left').setWidth(24) # previously 48

def sendCursorPos(self, plot):
    plot.scene().sigMouseMoved.connect(
                    lambda event, p=plot: guifuncs.getCursorPos(self, event, p)
                    )
    
def sendClickPos(self, plot):
    plot.scene().sigMouseClicked.connect(
                    lambda event, p=plot: guifuncs.addVerticalLine(self, event, p)
                    )
    
def playAlarm(parent, **kwargs):
    # Each 'cycle' of the alarm will have 4 beeps (3 short, 1 longer) and will
    # take exactly 1 second to complete
    while parent.beeping:
        for i in range(3):
            winsound.Beep(2500, 75) # frequency (Hz) and duration (ms)
            time.sleep(0.01)
        winsound.Beep(2500, 175)
        time.sleep(0.57)
    
def equalizeDataLengths(first, second):
    min_length = min(len(first), len(second))
    first = first[:min_length]
    second = second[:min_length]
    return first, second
    
def getSeconds():
    return float(str(time.time()-int(time.time()))[1:])

def rateLimiter(frequency) -> bool:
    '''
    frequency : float
        Frequency in Hertz.
    '''
    frequency = max(abs(frequency), 1e-3)
    t = getSeconds()
    quotient, remainder = divmod(t, 1./frequency)
    return False if remainder > 0.01 else True
