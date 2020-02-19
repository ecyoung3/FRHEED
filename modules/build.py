# -*- coding: utf-8 -*-
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

from PyQt5.QtWidgets import QPushButton, QLabel, QSizePolicy # GUI elements
from PyQt5.QtGui import QPixmap, QTabWidget, QTabBar
from PyQt5.QtCore import Qt # for the GUI
import configparser
from matplotlib import cm
import pyqtgraph as pg  # for plotting
import numpy as np
from PIL import Image, ImageQt  # for image processing
from colormap import Colormap

# =============================================================================
# 
# This module is used to build components of the UI. It is divided into parts
# which require camera initialization and those which do not (core UI).
#
# =============================================================================

from . import cameras, utils, guifuncs

def mainmenu(self, system):
    # Setting top menu bar functionality, i.e. what function is called when clicked
    self.menuExit.triggered.connect(self.closeEvent)
    dlg = cameras.selectionDialog(self)
    self.changesourceButton.triggered.connect(lambda: dlg.chooseCamera(system, quitting=False))
    self.menuChangeDirectory.triggered.connect(lambda: utils.setBasepath(self, change=True))
    
def toolbar(self):
    toolbuttons = {
                  'captureButton': lambda: self.grab_frame(),
                  'recordButton': lambda: guifuncs.recordVideo(self),
                   'liveplotButton': lambda: guifuncs.togglePlot(self),
                  'drawButton': lambda: guifuncs.showShapes(self),
                  'moveshapesButton': lambda: guifuncs.moveShapes(self),
                  'rectButton': lambda: guifuncs.cycleColors(self),
                  'fftButton': lambda: guifuncs.plotFFT(self),
                  'userButton': lambda: utils.setUser(self),
                  'sampleButton': lambda: utils.setSample(self),
                  'directoryButton': lambda: utils.openDirectory(),
                  }
    for button, function in toolbuttons.items():
        self.button = self.findChild(QPushButton, button)
        self.button.clicked.connect(function)
    
    # Zoom slider
    self.zoom = 0.5
    self.zoomvalueLabel.setText('{}%'.format(int(self.zoom*100)))
    self.zoomSlider.setValue(int(self.zoom*100))
    self.zoomSlider.valueChanged.connect(lambda: guifuncs.zoomImage(self))
    
    # Turn on autoscaling
    self.autoscaleCheckbox.setChecked(True)

def statusbar(self):
    # Add/edit statusbar items; this can only be done in the code (not in qt designer)
    self.mainstatus = QLabel()
    self.droppedframestatus = QLabel()
    self.messagestatus = QLabel()
    self.camerastatus = QLabel()
    self.fpsstatus = QLabel()
    self.serialstatus = QLabel()
    self.colormapstatus = QLabel()
    for b in (self.mainstatus, self.droppedframestatus, self.camerastatus, 
              self.fpsstatus, self.serialstatus, self.colormapstatus):
        b.setStyleSheet('''
            font: 11pt "Bahnschrift SemiLight"; 
            margin-bottom: 3px;
            margin-top: 3px;
            margin-left: 0px; 
            margin-right: 0px;
            ''')
        b.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
        b.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
    self.fpsstatus.setFixedWidth(90)
    self.mainstatus.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
    self.colormapstatus.setText('Current colormap: Gray')
    self.droppedframestatus.setText('Total dropped frames: 0 ')
    self.droppedframestatus.setFixedWidth(176)
    self.droppedframestatus.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
    # Add the statusbar widgets
    s = self.statusBar()
    s.addWidget(self.mainstatus)
    s.addPermanentWidget(self.droppedframestatus)
    s.addPermanentWidget(self.colormapstatus)
    s.addPermanentWidget(self.camerastatus)
    s.addPermanentWidget(self.serialstatus)
    s.addPermanentWidget(self.fpsstatus)
  
def splitters(self):
    # Change splitter behavior
    self.cam_index = self.topSplitter.indexOf(self.parentScrollArea) # get the index of the camera display in the splitter
    self.topSplitter.setCollapsible(self.cam_index, False) # make it so that the camera display can't be completely collapsed
    self.horizontalSplitter.setCollapsible(self.cam_index, False)
 
def annotation(self):
    # Annotation buttons
    self.annobgcolorButton.clicked.connect(lambda: guifuncs.annotationColor(self))
    self.annotextcolorButton.clicked.connect(lambda: guifuncs.annotationColor(self))
    
    # Defining the appearance of the annotation frame
    self.annotationFrame.setStyleSheet('background-color: {#19232d}; color: {white}')
    
    # Update the annotation text while typing
    self.setSampleName.textChanged.connect(lambda: guifuncs.annotationSampleText(self))
    self.setOrientation.textChanged.connect(lambda: guifuncs.annotationOrientationText(self))
    self.setGrowthLayer.textChanged.connect(lambda: guifuncs.annotationLayerText(self))
    self.setMisc.textChanged.connect(lambda: guifuncs.annotationMiscText(self))
    
    # Set annotation height
    self.anno_height = 70
        
def colormaps(self):
    # Define colormap
    cmp = Colormap()
    
    # Create custom colormap from black -> white with linear green gradient
    frheed_cmap = cmp.cmap_linear('black', 'green', 'white')
    
    # Register the custom colormap as a matplotlib colormap with name 'RHEEDgreen'
    cm.register_cmap(name='frheed_green', cmap=frheed_cmap)
    
    # Convert the colormap from the config file to a usable matplotlib format
    frheed_green = cm.get_cmap(name='frheed_green')
    cmaps = {
            'gist_gray': (cm.gist_gray, 0),
            'frheed_green': (frheed_green, 1),
            'hot': (cm.hot, 2),
            'plasma': (cm.plasma, 3),
            'seismic': (cm.seismic, 4),
            'hsv': (cm.hsv, 5),
            'viridis': (cm.viridis, 6),
            'cividis': (cm.cividis, 7),
            'magma': (cm.magma, 8),
            'inferno': (cm.inferno, 9),
            'gist_stern': (cm.gist_stern, 10),
            'ocean': (cm.ocean, 11),
            'gist_earth': (cm.gist_earth, 12),
            'terrain': (cm.terrain, 13),
            'jet': (cm.jet, 14),
            'nipy_spectral': (cm.nipy_spectral, 15),
            'cubehelix': (cm.cubehelix, 16),
            }
    gradient = np.linspace(0, 1, 500)
    gradient = np.vstack((gradient,)*34)
    for key in sorted(cmaps, key = lambda k: cmaps[k][1]):
        self.b = self.findChild(QPushButton, '{}Button'.format(key))
        # NOTE: 'state' must be passed as an argument because otherwise it will override the optional argument 'k'
        # and this button will emit the signal 'False' every time it's clicked.
        self.b.clicked.connect(lambda state, k=key: guifuncs.changeColormap(self, k))
        self.L = self.findChild(QLabel, '{}Label'.format(key))
        self.L.setPixmap(QPixmap.fromImage(ImageQt.ImageQt(Image.fromarray(np.uint8(cmaps[key][0](gradient)*255)))))

def timing(self):
    # Define actions of timer spinboxes
    for b in self.setHours, self.setMinutes, self.setSeconds:
        b.valueChanged.connect(guifuncs.changeTime)
    
    # Defining the starting displays of the timer and stopwatch screens
    self.stopwatchScreen.display('0.00')  # stopwatch screen display
    self.timerScreen.display('00:00:00.00')  # timer screen display
    
    # Timer and stopwatch button actions
    self.starttimerButton.clicked.connect(lambda: guifuncs.runTimer(self))
    self.resettimerButton.clicked.connect(lambda: guifuncs.resetTimer(self))
    self.startstopwatchButton.clicked.connect(lambda: guifuncs.runStopwatch(self))
    self.resetstopwatchButton.clicked.connect(lambda: guifuncs.clearStopwatch(self))
    
    # Setting stylesheets
    self.starttimerButton.setStyleSheet('color: #9be564') # green text
    self.startstopwatchButton.setStyleSheet('color: #9be564') # green text

def notebook(self):
    # Notepad buttons
    self.savenotesButton.clicked.connect(lambda: guifuncs.saveNotes(self))
    self.clearnotesButton.clicked.connect(lambda: guifuncs.clearNotes(self))

def plots(self):
    # The line below can be used to disable the Close button on specific tabs
    # QTabWidget.tabBar(self.oldDataTabs).setTabButton(0, QTabBar.RightSide, None)
    
    # Make it so the tab close buttons actually close that tab
    self.oldDataTabs.tabCloseRequested.connect(lambda i: self.oldDataTabs.removeTab(i))
    
    # Styling the area intensity data plots
    areaplots = [self.livePlotAxes, self.oldPlotAxes]
    fftplots = [self.plotFFTred, self.plotFFTgreen, self.plotFFTblue]
    allplots = areaplots + fftplots
    for p in allplots:
        p.plotItem.showGrid(True, True)
        
    for p in areaplots:
        p.setContentsMargins(0, 4, 10, 0)
        p.setLimits(xMin=0)
        p.setLabel('bottom', 'Time (s)')
    
def camsettings(self):
    # Load config options
    self.scaled_gamma = float(self.config['Default']['flir_gamma'])
    self.scaled_blacklevel = float(self.config['Default']['flir_blacklevel'])
    self.scaled_gain = float(self.config['Default']['flir_gain'])
    self.flir_exposure = float(self.config['Default']['flir_exposure'])
    self.usb_exposure = int(self.config['Default']['usb_exposure'])
   
    # Change text labels for profiles
    self.editProfile1Name.setText(self.config['Profile 1']['profile_name'])
    self.editProfile2Name.setText(self.config['Profile 2']['profile_name'])
    self.editProfile3Name.setText(self.config['Profile 3']['profile_name'])
    if self.camtype == 'USB':
        self.minexp = -13
        self.maxexp = -1
        self.changeExposure.setRange(self.minexp, self.maxexp)
        self.changeExposure.setSuffix('')
        self.changeExposure.setSingleStep(1.0)
        self.changeExposure.setDecimals(0)
        self.changeExposure.setValue(self.usb_exposure)
        for b in (self.gainSlider, self.gammaSlider, self.blacklevelSlider):
            b.setEnabled(False)
        self.camerastatus.setText('Connected to USB camera')
        self.serialstatus.setText('S/N: ')
        self.fpsstatus.setText('FPS: ')
    if self.camtype == 'FLIR':
        self.minexp = 0.011
        self.maxexp = 29999.998
        self.changeExposure.setRange(self.minexp, self.maxexp)
        self.changeExposure.setValue(self.flir_exposure/1000)
        self.changeExposure.setSingleStep(0.5)
        self.changeExposure.setDecimals(3)
        self.gammaSlider.valueChanged.connect(lambda: guifuncs.setGamma(self))
        self.gammaValue_Label.setText("{:.2f}".format(self.scaled_gamma)) # update box that displays Gamma value
        self.blacklevelSlider.valueChanged.connect(lambda: guifuncs.setBlackLevel(self))
        self.blacklevelValue_Label.setText("{:.2f}".format(self.scaled_blacklevel)) # update box that displays Black Level value
        self.gainSlider.valueChanged.connect(lambda: guifuncs.setGain(self))
        self.gainValue_Label.setText("{:.2f}".format(self.scaled_gain))
       
    # Show the serial number of the connected camera (if it has one)
    guifuncs.showSerial(self)

def cambuttons(self):
    # Invert image
    self.invertButton.clicked.connect(lambda: guifuncs.invertImage(self))
    
    # Background settings
    self.backgroundButton.clicked.connect(lambda: guifuncs.setBackground(self))
    self.clearbgButton.clicked.connect(lambda: guifuncs.clearBackground(self))
    self.clearbgButton.setEnabled(False)
    
    # Changing exposure
    self.defaultconditionsButton.clicked.connect(lambda: guifuncs.setDefaultConditions(self))
    
    # Defining what happens when spinboxes (boxes with numbers and up/down arrows to change values) and sliders are changed
    self.changeExposure.valueChanged.connect(lambda: guifuncs.setExposure(self))
    
    # Buttons for saving and loading image profiles
    for b in (self.loadProfile1, self.loadProfile2, self.loadProfile3, 
              self.saveProfile1, self.saveProfile2, self.saveProfile3):
        b.clicked.connect(lambda: guifuncs.setImageProfile(self))

def variables(self):
    self.inverted = False
    self.background = None
    self.backgroundset = False
    self.droppedframes = 0
    self.framecount = 0
    self.img_number = 0
    self.vid_number = 0
    self.realfps = None
    self.recording = False
    self.plotting = False
    self.readytoplot = False
    self.drawing = False
    self.visibleshapes = True
    self.timeset, self.savedtime, self.savedtime2, self.totaltime = 0.0, 0.0, 0.0, 0.0
    self.hours, self.minutes, self.seconds = 0.0, 0.0, 0.0
    self.shapes = {
        'red': {
            'start': None,
            'end':   None,
            'color': (228, 88, 101),
            'time': [],
            'data': [],
            'plot': self.livePlotAxes.plot(
                        pen = pg.mkPen((228, 88, 101), width=1, ), 
                        clear = True),            
            },
        'green': {
            'start': None,
            'end':   None,               
            'color': (155, 229, 100),
            'time': [],
            'data': [],
            'plot': self.livePlotAxes.plot(
                        pen = pg.mkPen((155, 229, 100), width=1), 
                        clear = False),            
            },
        'blue': {
            'start': None,
            'end':   None,
            'color': (0, 167, 209),
            'time': [],
            'data': [],
            'plot': self.livePlotAxes.plot(
                        pen = pg.mkPen((0, 167, 209), width=1), 
                        clear = False),            
            },
        'orange': {
            'start': None,
            'end':   None,
            'color': (244, 187, 71),
            'time': [],
            'data': [],
            'plot': self.livePlotAxes.plot(
                        pen = pg.mkPen((244, 187, 71), width=1), 
                        clear = False),            
            },
        'purple': {
            'start': None,
            'end':   None,
            'color': (125, 43, 155),
            'time': [],
            'data': [],
            'plot': self.livePlotAxes.plot(
                        pen = pg.mkPen((125, 43, 155), width=1), 
                        clear = False),
            },
        }
    self.colorindex = 0
    self.activecolor = list(self.shapes.keys())[self.colorindex]

def core_ui(self):
    variables(self)
    toolbar(self)
    statusbar(self)
    splitters(self)
    annotation(self)
    colormaps(self)
    timing(self)
    notebook(self)
    plots(self)
    
def camera_ui(self):
    camsettings(self)
    cambuttons(self)