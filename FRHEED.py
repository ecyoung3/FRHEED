#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""FRHEED

This is a real-time RHEED (Reflection High Energy Electron Diffraction)
analysis program designed for use with USB or FLIR GigE cameras.

Author: Elliot Young
        Materials Department
        University of California, Santa Barbara
        Chris Palmstrøm Research Group
        ecyoung@ucsb.edu

Originally created October 2018.

Github: https://github.com/ecyoung3/FRHEED

"""


import os  # for checking/creating computer directories
import sys  # for system-specific parameters

import configparser  # for reading a configuration file
import cv2  # for image processing
import numpy as np  # for math and array processing
import queue  # for handling threads
import threading  # for threading
import time  # for keeping track of time

from colormap import Colormap  # for creating custom colormaps
from matplotlib import cm  # for using colormaps
from PIL import Image, ImageQt  # for image processing
from PyQt5 import QtCore, QtGui, uic, QtWidgets  # for the GUI
import pyqtgraph as pg  # for plotting
from scipy.fftpack import rfft  # for performing real FFT on data

# Import PySpin if it exists on the system
try:
    import PySpin
    importedPySpin = True
except ImportError:
    importedPySpin = False

os.path.expanduser('~')

# Define global variables
capture_thread = None  # no capture thread until defined at end of program
running = False  # capture thread not running
isfile = False  # file name not set
recording = False  # not recording video
setout = False  # output location not set
liveplotting = False  # not live-plotting data
drawing = False  # shapes not being shown
backgroundset = False  # not subtracting background image
runstopwatch = False  # stopwatch starts from set value
stopwatch_active = False  # stopwatch is not running
timer_active = False  # timer starts from zero
timing = False  # timer is not running
inverted = False  # image is not inverted
averaging = False  # pixel intensity data is not being averaged
summing = True  # pixel intensity data is being summed
movingshapes = False  # not moving shapes translationally
red, green, blue = True, False, False  # Editing red triangle by default
imnum = 1  # first image number is 1
vidnum = 1  # first video number is 1
t0 = time.time()  # set start time is when program is opened

# Initialize all variables for frame intensity plotting as empty arrays
(t, avg1, avg2, avg3,  # variables for live plot
 oldt, oldavg1, oldavg2, oldavg3,  # variables for most recently collected data
 oldert, olderavg1, olderavg2, olderavg3,  # variables for older data
 background) = ([], ) * 13  # frame for background subtraction is empty

# Default dimensions of rectangles: 640x480 centered in upper left corner (0,0)
x1, y1, x2, y2 = 0, 0, 640, 480  # red rectangle
a1, b1, a2, b2 = 0, 0, 640, 480  # green rectangle
c1, d1, c2, d2 = 0, 0, 640, 480  # blue recta-ngle

# basecoords are used to define starting positiion when adjusting shapes
basecoords = (x1, x2, y1, y2, a1, a2, b1, b2, c1, c2, d1, d2)
i = 1  # Index for which color rectangle is currently active: 1 = red, 2 = green, 3 = blue

# Enable manual calculation for RHEED peaks
ic = kc = jc = True

# Default filename if nothing is selected
filename = 'default'

# Loading UI file from qt designer
form_class = uic.loadUiType("FRHEED.ui")[0]  # UI file should be located in same directory as this script

# Define "shortcut" for queue
q = queue.Queue()

# Define video recording codec
fourcc = cv2.VideoWriter_fourcc(*'MJPG') # MJPG works with .avi

# Set default appearance of plots
pg.setConfigOption('background', 'w')  # 'w' = white background
pg.setConfigOption('foreground', 0.0)  # black axes lines and labels

# Initialize configuration file
config = configparser.ConfigParser()  # create 'shortcut' for configparser
config.read('config.ini')  # config file is named 'config.ini' and should be in the same directory as this .py file

# Select default save location if none set
if config['Default']['pathset'] == 'False':
    warning = QtWidgets.QMessageBox.warning(None,  'Notice', 'Please select a base directory for saving files.')
    file = str(QtWidgets.QFileDialog.getExistingDirectory(None, 'Select Save Directory'))  # open file location dialog
    config['Default']['pathset'] = 'True'  # change config option to True
    config['Default']['path'] = str(file+'/')  # add / to end of path name
    with open('config.ini', 'w') as configfile:  # update the config file
        config.write(configfile)

# Set base path to config
basepath = config['Default']['path']

# Create basepath directory if it doesn't exist for some reason
if not os.path.exists(basepath):  # check if directory exists
    os.makedirs(basepath)  # create directory if it doesn't exist

# Set colormap to config
cmap = config['Default']['cmap']

# Set camera type from config
camtype = config['Default']['cameratype']

# Set grower and sample name from config
grower = config['Default']['grower']
samplename = config['Default']['sample']

# Set total path
path = str(basepath+grower+'/'+samplename+'/')


# If USB button clicked: set camtype config option to 'USB' then close popup; must be defined before popup window
def usb(self):
    global camtype, config
    camtype = 'USB'
    config['Default']['cameratype'] = camtype
    with open('config.ini', 'w') as configfile:
        config.write(configfile)
    dialog.close()


# IF FLIR button clicked: set camtype config option to 'FLIR' then close popup; must be defined before popup window
def FLIR(self):
    global camtype, config
    camtype = 'FLIR'
    config['Default']['cameratype'] = camtype
    with open('config.ini', 'w') as configfile:
        config.write(configfile)
    dialog.close()


# Prompt user to select type of camera if not set in config
if 'USB' not in camtype and 'FLIR' not in camtype:
    dialog = QtWidgets.QDialog()  # create new dialog window
    icon = QtGui.QIcon('FRHEED icon.ico')  # set icon of dialog window; icon file should be in this same directory
    dialog.setWindowIcon(icon)  # set popup window icon
    dialog.setWindowTitle('Select Camera Type')  # set title of window
    dialog.verticalLayout = QtWidgets.QVBoxLayout(dialog)  # create vertical layout for window
    # Add label with text
    dialog.text = QtWidgets.QLabel()
    dialog.text.setText('Which type of camera would you like to connect to?')
    dialog.verticalLayout.addWidget(dialog.text)
    # Add button that says 'USB'
    dialog.button1 = QtWidgets.QPushButton()  # create first button
    dialog.button1.setText('USB')  # set button text
    dialog.verticalLayout.addWidget(dialog.button1)  # add the first button to the layout, below the text
    dialog.button1.clicked.connect(usb)  # button 1 triggers 'USB' function when clicked (line 135)
    dialog.button2 = QtWidgets.QPushButton()  # create second button
    dialog.button2.setText('FLIR Gigabit Ethernet')  # set button text
    dialog.verticalLayout.addWidget(dialog.button2)  # add second button to layout, below the first button
    dialog.button2.clicked.connect(FLIR)  # button 2 triggers 'FLIR' function when clicked (line 145)
    dialog.exec_()  # execute the dialog window to make it appear

# Set exposure depending on type of camera
if camtype == 'FLIR':
    exposure = float(100000)  # value in microseconds = 100 milliseconds
if camtype == 'USB':
    exposure = -5  # exposure range for most webcams is -14 to -1

# Define colormap
cmp = Colormap()

# Create custom colormap from black -> white with linear green gradient
FRHEEDcmap = cmp.cmap_linear('black', 'green', 'white')

# Register the custom colormap as a matplotlib colormap with name 'RHEEDgreen'
cm.register_cmap(name='RHEEDgreen', cmap=FRHEEDcmap)

# Convert the colormap from the config file to a usable matplotlib format
cmap = cm.get_cmap(name=cmap)  # convert config cmap to the matplotlib format

# Connect to FLIR gigabyte ethernet (GigE) camera if PySpin is imported and camera type is set to 'FLIR'
if importedPySpin and config['Default']['cameratype'] == 'FLIR':
    # TODO make this code more generic to connect to any camera and add error handling
    system = PySpin.System.GetInstance()  # start new instance
    cam_list = system.GetCameras()  # get list of cameras
    cam = cam_list.GetBySerial("18434385")  # get the specific VG camera
    nodemap_tldevice = cam.GetTLDeviceNodeMap()  # idk what this does
    cam.Init()  # initialize camera
    cam.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)  # disable auto exposure
    cam.ExposureTime.SetValue(exposure)  # set exposure time in microseconds
    time.sleep(0.01)  # wait for things to initialize
    nodemap = cam.GetNodeMap()  # gets a list of camera options/functions (?)
    node_acquisition_mode = PySpin.CEnumerationPtr(nodemap.GetNode("AcquisitionMode"))
    node_acquisition_mode_continuous = node_acquisition_mode.GetEntryByName("Continuous")
    acquisition_mode_continuous = node_acquisition_mode_continuous.GetValue()  # get continuous acquisition mode
    node_acquisition_mode.SetIntValue(acquisition_mode_continuous)  # set continuous acquisition mode
    cam.BeginAcquisition()  # begin acquiring data from the camera

# Initialize USB camera, if selected
if camtype == 'USB':
    # TODO check if camera in slot '0' actually exists and throw an error if it doesn't
    cam = cv2.VideoCapture(0)  # grab frames from webcam in slot 0
    cam.set(cv2.CAP_PROP_EXPOSURE, exposure)  # set camera exposure


# Code for grabbing frames from camera in threaded loop
def grab(fps, queue):
    global running, recording, out, setout, cam, inverted, camtype, cmap, path, filename, vidx, vidy
    #
    # This is the main 'while' loop that utilizes threading to grab frames from the camera
    # Without threading, the program would run much more slowly and the GUI would hang during operation
    #
    while running:
        frame = {}
        if camtype == 'FLIR':
            image_result = cam.GetNextImage()  # get image from FLIR GigE camera buffer
            img = image_result.GetNDArray()  # grab image as a numpy array
        if camtype == 'USB':
            grabbed, img = cam.read()  # read frame from webcam; grabbed = True if the frame isn't empty
            if cam.isOpened():
                if grabbed:
                    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)  # convert webcam to grayscale
            if not cam.isOpened():
                print('No camera detected')
        frame["img"] = img
        if queue.qsize() < 50:
            queue.put(frame)
            if recording:
                if not setout:
                    setout = True
                if inverted:
                    img = np.invert(img)
                img = cv2.resize(img, dsize=(int(vidx), int(vidy)), interpolation=cv2.INTER_CUBIC)
                imc = np.uint8(cmap(img)*255)
                imc = imc[:, :, 0:3]
                imc = cv2.cvtColor(imc, cv2.COLOR_RGB2BGR)
                out.write(imc)


# This is the code for the main FRHEED program window. The UI is coded in qt designer and saved as a FRHEED.ui file.
# There are also certain file dependencies that the UI uses, which should be included on Github.
class FRHEED(QtWidgets.QMainWindow, form_class):
    global config

    def __init__(self, parent=None):
        # TODO make this section look prettier
        global samplename, exposure, x1, y1, x2, y2, grower, camtype, config
        QtWidgets.QMainWindow.__init__(self, parent)  # initialize the main window
        self.setupUi(self)  # this is where the UI is actually constructed from the FRHEED.ui file

        # Defining local variables (these can be called by self.VAR_NAME by functions within the FRHEED class)
        # These need to be defined here to avoid errors in later class functions that call them; for example, if the
        # camera feed stops displaying, it is likely because the update_frame loop is attempting to use a variable that
        # is not defined earlier in the code.
        self.oldwidth = self.parentFrame.frameSize().width()
        self.oldheight = self.parentFrame.frameSize().height()
        self.drawingshapes = False
        self.timeset = 0.0
        self.savedtime = 0.0
        self.savedtime2 = 0.0
        self.livecursor, self.newercursor, self.oldercursor = '', '', ''  # cursor positions on intensity data plots
        self.redcursor, self.greencursor, self.bluecursor = '', '', ''  # cursor positions on FFT plots
        self.rheed1cal, self.rheed2cal, self.rheed3cal = '', '', ''  # text for manually calculated RHEED oscillation
        self.highexposuretime = int(config['Default']['highexposure'])
        self.lowexposuretime = int(config['Default']['lowexposure'])

        # Defining function and appearance of buttons that are dependent upon the type of camera being used
        # The UI by default is setup for FLIR/GigE cameras, which mainly has to do with valid exposure settings
        if camtype == 'USB':
            self.changeExposure.setRange(-14, -1)
            self.changeExposure.setValue(int(config['Default']['lowexposure']))
            self.changeExposureTime.setEnabled(False)
            self.lowexposureButton.setText('Set Low Exposure')
            self.highexposureButton.setText('Set High Exposure')
            self.setLowExposure.setRange(-14, -1)
            self.setLowExposure.setValue(int(config['Default']['lowexposure']))
            self.setHighExposure.setRange(-14, -1)
            self.setHighExposure.setValue(int(config['Default']['highexposure']))

        # Defining text and appearance of buttons
        self.rectButton.setStyleSheet('QPushButton {color:red}')  # make the text color of the rectangle button red
        self.starttimerButton.setStyleSheet('QPushButton {color:green}')
        self.startstopwatchButton.setStyleSheet('QPushButton {color:green}')

        # Defining the appearance of the annotation frame
        p = self.annotationFrame.palette()  # create object to edit palette of the annotation frame
        p.setColor(self.annotationFrame.backgroundRole(), QtCore.Qt.black)  # make the annotation background black
        self.annotationFrame.setPalette(p)  # apply the palette to the annotation frame to update its color
        self.annotateLayer.setStyleSheet('QLabel {color:white}')  # make the annotation text white
        self.annotateMisc.setStyleSheet('QLabel {color:white}')
        self.annotateOrientation.setStyleSheet('QLabel {color:white}')
        self.annotateSampleName.setStyleSheet('QLabel {color:white}')
        # TODO eventually remove the pixmaps and just plot things directly from the matplotlib library
        self.grayscaleSample.setPixmap(QtGui.QPixmap('gray colormap.png'))  # display the sample for the  gray colormap
        self.greenSample.setPixmap(QtGui.QPixmap('green colormap.png'))  # display the sample for the green colormap
        self.hotSample.setPixmap(QtGui.QPixmap('hot colormap.png'))  # display the sample for the hot colormap
        self.plasmaSample.setPixmap(QtGui.QPixmap('plasma colormap.png'))  # display the sample for the plasma colormap

        # Defining the starting displays of the timer and stopwatch screens
        self.stopwatchScreen.display('0.00')  # stopwatch screen display
        self.timerScreen.display('00:00:00.00')  # timer screen display

        # Setting button functionality, i.e. what function is called when clicked
        self.captureButton.clicked.connect(self.capture_image)
        self.recordButton.clicked.connect(self.record)
        self.liveplotButton.clicked.connect(self.liveplot)
        self.drawButton.clicked.connect(self.showShapes)
        self.moveshapesButton.clicked.connect(self.moveshapes)  # this doesn't do anything for now
        self.rectButton.clicked.connect(self.selectColor)
        self.fftButton.clicked.connect(self.plotFFT)
        self.growerButton.clicked.connect(self.changeGrower)
        self.sampleButton.clicked.connect(self.changeSample)
        self.directoryButton.clicked.connect(self.openDirectory)
        self.savenotesButton.clicked.connect(self.saveNotes)
        self.clearnotesButton.clicked.connect(self.clearNotes)
        self.grayscaleButton.clicked.connect(self.mapGray)
        self.greenButton.clicked.connect(self.mapGreen)
        self.plasmaButton.clicked.connect(self.mapPlasma)
        self.hotButton.clicked.connect(self.mapHot)
        self.backgroundButton.clicked.connect(self.setbackground)
        self.clearbackgroundButton.clicked.connect(self.clearbackground)
        self.invertButton.clicked.connect(self.invert)
        self.lowexposureButton.clicked.connect(self.lowexposure)
        self.highexposureButton.clicked.connect(self.highexposure)
        self.starttimerButton.clicked.connect(self.timer)
        self.resettimerButton.clicked.connect(self.resettimer)
        self.startstopwatchButton.clicked.connect(self.stopwatch)
        self.resetstopwatchButton.clicked.connect(self.clearstopwatch)

        # Setting top menu bar functionality, i.e. what function is called when clicked
        self.menuExit.triggered.connect(self.closeEvent)
        self.connectButton.triggered.connect(self.connectCamera)

        # Defining what happens when spinboxes (boxes with numbers and up/down arrows to change values) are changed
        self.changeExposure.valueChanged.connect(self.setExposure)
        self.changeExposureTime.valueChanged.connect(self.setExposureTime)
        self.setHours.valueChanged.connect(self.changetime)
        self.setMinutes.valueChanged.connect(self.changetime)
        self.setSeconds.valueChanged.connect(self.changetime)
        # Create window for live data plotting
        self.plot1.plotItem.showGrid(True, True)
        self.plot1.plotItem.setContentsMargins(0, 4, 10, 0)
        self.plot1.setLimits(xMin=0)
        self.plot1.setLabel('bottom', 'Time (s)')
        self.proxy1 = pg.SignalProxy(self.plot1.scene().sigMouseMoved, rateLimit=60, slot=self.mouseMoved1)
        self.proxy2 = pg.SignalProxy(self.plot2.scene().sigMouseMoved, rateLimit=60, slot=self.mouseMoved2)
        self.proxy3 = pg.SignalProxy(self.plot3.scene().sigMouseMoved, rateLimit=60, slot=self.mouseMoved3)
        self.proxy4 = pg.SignalProxy(self.plotFFTred.scene().sigMouseMoved, rateLimit=60, slot=self.mouseMoved4)
        self.proxy5 = pg.SignalProxy(self.plotFFTgreen.scene().sigMouseMoved, rateLimit=60, slot=self.mouseMoved5)
        self.proxy6 = pg.SignalProxy(self.plotFFTblue.scene().sigMouseMoved, rateLimit=60, slot=self.mouseMoved6)
        self.plot2.plotItem.showGrid(True, True)
        self.plot2.plotItem.setContentsMargins(0, 4, 10, 0)
        self.plot2.setLimits(xMin=0)
        self.plot2.setLabel('bottom', 'Time (s)')
        self.plot3.plotItem.showGrid(True, True)
        self.plot3.plotItem.setContentsMargins(0, 4, 10, 0)
        self.plot3.setLimits(xMin=0)
        self.plot3.setLabel('bottom', 'Time (s)')
        self.redpen = pg.mkPen('r', width=1, style=QtCore.Qt.SolidLine)  # plot first line with red pen, 'r'
        self.greenpen = pg.mkPen('g', width=1, style=QtCore.Qt.SolidLine)  # plot first line with green pen, 'g'
        self.bluepen = pg.mkPen('b', width=1, style=QtCore.Qt.SolidLine)  # plot first line with blue pen, 'b'
        # Create window for FFT plot
        self.plotFFTred.plotItem.showGrid(True, True)
        self.plotFFTred.plotItem.setContentsMargins(0, 4, 10, 0)
        self.plotFFTred.setLabel('bottom', 'Frequency (Hz)')
        self.plotFFTgreen.plotItem.showGrid(True, True)
        self.plotFFTgreen.plotItem.setContentsMargins(0, 4, 10, 0)
        self.plotFFTgreen.setLabel('bottom', 'Frequency (Hz)')
        self.plotFFTblue.plotItem.showGrid(True, True)
        self.plotFFTblue.plotItem.setContentsMargins(0, 4, 10, 0)
        self.plotFFTblue.setLabel('bottom', 'Frequency (Hz)')
        # Set timer to update the GUI every 1 millisecond
        self.timer = QtCore.QTimer(self)  # create timer object
        self.timer.timeout.connect(self.update_frame)  # run the 'update_frame' function every millisecond
        self.timer.start(1)  # time in milliseconds

    # Start grabbing camera frames when Camera -> Connect is clicked
    def connectCamera(self):
        global running, grower, isfile, samplename, path, imnum, vidnum, basepath, grower, capture_thread
        if len(grower) == 0:
            grower, ok = QtWidgets.QInputDialog.getText(w, 'Enter grower', 'Who is growing? ')
            if ok:
                imnum, vidnum = 1, 1
                path = str(basepath+grower+'/')
                if not os.path.exists(path):
                    os.makedirs(path)
            else:
                QtWidgets.QMessageBox.warning(self, 'Error', 'Grower not set')
                return
        if len(samplename) == 0:
            samplename, ok = QtWidgets.QInputDialog.getText(w, 'Change sample name', 'Enter sample name: ')
            if ok:
                imnum, vidnum = 1, 1
                isfile = True
                path = str(basepath+grower+'/'+samplename+'/')
                # Create folder to save images in if it doesn't already exist
                if not os.path.exists(path):
                    os.makedirs(path)
            else:
                QtWidgets.QMessageBox.warning(self, 'Error', 'Grower not set')
                return
        running = True
        capture_thread.start()
        self.connectButton.setEnabled(False)
        self.connectButton.setText('Connecting...')
        self.statusbar.showMessage('Starting camera...')

    # Change camera exposure
    def setExposure(self):
        global exposure, cam, camtype
        expo = self.changeExposure.value()
        if camtype == 'FLIR':
            exposure = float(1.2**expo)  # exponential scale for exposure (time in microseconds)
            self.changeExposureTime.setValue(int(exposure / 1000.0))
            cam.ExposureTime.SetValue(exposure)
        if camtype == 'USB':
            cam.set(cv2.CAP_PROP_EXPOSURE, expo)  # setting webcam exposure

    # Set exposure time
    def setExposureTime(self):
        global exposure, cam, camtype
        expotime = self.changeExposureTime.value()
        exposure = float(expotime * 1000)
        cam.ExposureTime.SetValue(exposure)

    # Preset high exposure for taking images
    def highexposure(self):
        global exposure, cam, camtype
        expo = self.setHighExposure.value()
        if camtype == 'FLIR':
            val = str(1000*expo)
            cam.ExposureTime.SetValue(val)
            config['VG']['highexposure'] = str(val)
            # Update the high exposure default in the config file
            with open('config.ini', 'w') as configfile:
                config.write(configfile)
        if camtype == 'USB':
            cam.set(cv2.CAP_PROP_EXPOSURE, expo)  # setting webcam exposure
            config['Default']['highexposure'] = str(expo)
            # Update the high exposure default in the config file
            with open('config.ini', 'w') as configfile:
                config.write(configfile)

    # Preset low exposure for taking RHEED oscillations
    def lowexposure(self):
        global exposure, cam, camtype
        expo = int(self.setLowExposure.value())
        if camtype == 'FLIR':
            val = str(1000*expo)
            cam.ExposureTime.SetValue(val)
            config['VG']['lowexposure'] = str(val)
            # Update the high exposure default in the config file
            with open('config.ini', 'w') as configfile:
                config.write(configfile)
        if camtype == 'USB':
            cam.set(cv2.CAP_PROP_EXPOSURE, expo)  # setting webcam exposure
            config['Default']['lowexposure'] = str(expo)
            # Update the high exposure default in the config file
            with open('config.ini', 'w') as configfile:
                config.write(configfile)

    # Protocol for updating the video frames in the GUI
    def update_frame(self):
        # Defining global variables. I know this isn't the best way of doing it, but you'll have to live with it.
        global p, x1, y1, x2, y2, a1, b1, a2, b2, c1, d1, c2, d2, basecoords  # integer globals
        global t0, t, tstart, avg1, avg2, avg3  # floating point globals # noqa
        global background  # numpy array globals
        global running, averaging, summing, movingshapes, inverted, backgroundset  # boolean globals
        global runstopwatch, stopwatch_active, timing, timer_active  # boolean globals related to timer/stopwatch
        global samplename, grower  # string globals
        global cmap  # matplotlib colormap global
        global q  # for interacting with the queue (getting frames from camera)

        # Record the width and height of the parent frame, which contains the camera feed and shape drawing canvas
        self.window_width = self.parentFrame.frameSize().width()
        self.window_height = self.parentFrame.frameSize().height()

        # Connect to the camera on startup
        if not running:
            self.connectCamera()

        # Perform the following code if the queue is not empty (i.e. the camera is running)
        if not q.empty():
            # Set camera connect button text to 'Connected' so long as the thread is running
            self.connectButton.setText('Connected')

            # Collect all coordinates for drawing rectangles in one variable; used as reference when adjusting shape
            if self.drawingshapes:
                basecoords = (x1, x2, y1, y2, a1, a2, b1, b2, c1, c2, d1, d2)

            # Get the current camera frame from the threading queue
            frame = q.get()  # get the latest object from the queue
            img = frame["img"]  # get the actual numpy array for the image

            # Invert the image if the option has been selected
            if inverted:
                img = np.invert(img)

            # Subtract a background image if it has been set
            if backgroundset:
                img = img - background

            # Scaling the image from the camera
            img_height, img_width = img.shape[0], img.shape[1]  # img.shape gives image dimensions as (height, width)
            scale_w = float(self.window_width) / float(img_width)  # calculate the width scale
            scale_h = float(self.window_height) / float(img_height)  # calculate the height scale
            scale = min([scale_w, scale_h])  # set the scale to the minimum of the width and height scales
            self.scaled_w = int(scale * img_width)  # calculate the scaled width as an integer (important)
            self.scaled_h = int(scale * img_height)  # calculate the scaled height as an integer (important)

            # Resize camera canvas (displays camera feed) and draw canvas (displays shapes) to proper size
            self.cameraCanvas.resize(self.scaled_w, self.scaled_h)
            self.drawCanvas.resize(self.scaled_w, self.scaled_h)

            # Resize annotation frame to the width of the camera feed and keep the height constant
            # TODO reduce flickering of annotation frame when resizing window (using pixmap as black background)
            self.annotationFrame.resize(self.scaled_w, 56)

            # Resize the image to the new scaled width and height.
            # Linear interpolation (INTER_LINEAR) would be slightly faster but produce a lower quality image.
            img = cv2.resize(img, dsize=(self.scaled_w, self.scaled_h), interpolation=cv2.INTER_CUBIC)
            self.f = np.uint8(cmap(img)*255)  # apply colormap to the numpy array; mult. by 255 since cmap scales to 1

            # Apply colormap to the image array and convert it to a PIL image object
            self.img = Image.fromarray(self.f)

            # Convert PIL image to QImage that can be applied to a QLabel as a QPixmap
            imc = ImageQt.ImageQt(self.img)

            # Create a pixmap from the QImage and display it on the camera canvas
            self.cameraCanvas.setPixmap(QtGui.QPixmap.fromImage(imc))

            # Resize the rectangles if the main window size changes
            if self.oldwidth != self.window_width or self.oldheight != self.window_height:
                newcoords = list(map(lambda x: int(x*scale), basecoords))  # this just scales all coordinates equally
                x1, x2, y1, y2, a1, a2, b1, b2, c1, c2, d1, d2 = newcoords  # collect the updated rectangle coordinates

            # Updating and plotting live intensity data
            if liveplotting:

                # This section sorts coordinates such that x1 < x2 so taking the mean doesn't return a null value
                c = [(x1, x2), (y1, y2), (a1, a2), (b1, b2), (c1, c2), (d1, d2)]  # create list of tuples to be sorted
                k = []  # define k as an empty array

                # Sort each pair such that the first value is always the smaller of the two i.e. (2, 1) -> (1, 2)
                for i in range(len(c)):
                    j = sorted(c[i])  # the 'sorted' function sorts the i'th tuple in c in ascending order
                    k.append(j)  # append the sorted tuple to the array, k

                # If the values in a tuple are equal, add 1 to the second value so taking the mean is still valid
                for i in range(len(k)):
                    if k[i][0] == k[i][1]:
                        k[i][1] = k[i][0] + 1

                # Update the coordinates so that they're sorted properly and can be used to calculate mean values
                [(x1a, x2a), (y1a, y2a), (a1a, a2a), (b1a, b2a), (c1a, c2a), (d1a, d2a)] = k

                # Take the averages of the defined area if the averaging method is selected (default disabled)
                if averaging:
                    avg_1 = img[y1a:y2a, x1a:x2a].mean()  # take the average of the region enclosed by the red rectangle
                    avg_1 = round(avg_1, 3)  # round to 3 decimal places
                    avg_2 = img[b1a:b2a, a1a:a2a].mean()  # average of intensities in green rectangle
                    avg_2 = round(avg_2, 3)
                    avg_3 = img[d1a:d2a, c1a:c2a].mean()  # average of intensities in blue rectangle
                    avg_3 = round(avg_3, 3)

                # Sum the intensity of every enclosed pixel if the summing method is selected (default enabled)
                if summing:
                    avg_1 = img[y1a:y2a, x1a:x2a].sum()  # sum the intensity of every pixel in the red rectangle
                    avg_1 = round(avg_1, 3)  # round to 3 decimal places
                    avg_2 = img[b1a:b2a, a1a:a2a].sum()  # sum of intensities in green rectangle
                    avg_2 = round(avg_2, 3)
                    avg_3 = img[d1a:d2a, c1a:c2a].sum()  # sum of intensities in blue rectangle
                    avg_3 = round(avg_3, 3)

                # Append the calculated average (or sum) to the data used for live plotting
                avg1.append(avg_1)  # avg1 is the data from the red rectangle
                avg2.append(avg_2)  # avg2 is the data from the green rectangle
                avg3.append(avg_3)  # avg3 is the data from the blue rectangle
                timenow = time.time() - t0  # update current time
                t.append(timenow)  # append current time to time data

                # Updating the live plot for the data using red, green, and blue lines (pens defined in init)
                curve1 = self.plot1.plot(pen=self.redpen, clear=True)  # clear = True to make live plotting faster
                curve2 = self.plot1.plot(pen=self.greenpen)  # don't use clear = True or the red plot won't show up
                curve3 = self.plot1.plot(pen=self.bluepen)  # don't use clear = True or the red & green plots won't show

                # Updating the data for each curve
                curve1.setData(t, avg1)
                curve2.setData(t, avg2)
                curve3.setData(t, avg3)

            # Drawing/displaying shapes on top of the camera feed
            if drawing:
                self.drawCanvas.raise_()  # this ensures that the shapes appear on top of the camera frame
                pixmap = QtGui.QPixmap(self.scaled_w, self.scaled_h)  # create a pixmap with same dimensions as camera
                pixmap.fill(QtGui.QColor("transparent"))  # make the pixmap transparent so the camera is visible
                qp = QtGui.QPainter(pixmap)  # initiate a painting event on the pixmap
                #
                # When drawing rectangles, (0, 0) is defined as the top left corner and down is +y, right is +x
                # The first two values indicate the top leftmost point of the rectangle and the last two values indicate
                # the width and height of the rectangle, respectively
                #
                qp.setPen(QtGui.QPen(self.redpen))  # use the same pen used to draw the plot (1px wide, solid red color)
                self.redrect = qp.drawRect(x1, y1, x2-x1, y2-y1)  # draw the red rectangle
                qp.setPen(self.greenpen)  # switch the pen to the green pen
                self.greenrect = qp.drawRect(a1, b1, a2 - a1, b2 - b1)  # draw the green rectangle
                qp.setPen(self.bluepen)  # switch the pen to the blue pen
                self.bluerect = qp.drawRect(c1, d1, c2 - c1, d2 - d1)  # draw the blue rectangle
                qp.end()  # end the painting event (it will get started again next update)
                self.drawCanvas.setPixmap(pixmap)  # update the canvas with the drawn-on pixmap containing the shapes
            # Record the width and height of the window so that changes in window size can be detected
            # This is used so the code knows when to scale the size of the drawn shapes
            self.oldwidth, self.oldheight = self.window_width, self.window_height
            # Similarly, record the current scale so that the shapes don't end up scaling exponentially
            self.relativescale = scale

        # Update labels and buttons with the appropriate text. This code should eventually be moved to sections outside
        # of this continuously updating loop, i.e. only when the window is initialized or grower/sample is changed.
        self.sampleLabel.setText('Current Sample: '+samplename)
        self.growerLabel.setText('Current Grower: '+grower)
        # Update the annotation preview as the user types their input
        self.annotateSampleName.setText('Sample: '+self.setSampleName.text())  # sample name
        self.annotateSampleName.resize()
        self.annotateOrientation.setText('Orientation: '+self.setOrientation.text())  # orientation
        self.annotateLayer.setText('Growth layer: '+self.setGrowthLayer.text())  # current growth layer
        self.annotateMisc.setText('Other notes: '+self.setMisc.text())  # other notes

        # Update the labels that display the coordinates of the current cursor position
        self.cursorLiveData.setText(self.livecursor)  # cursor position on the live plot
        self.cursorNewerData.setText(self.newercursor)  # newer plot
        self.cursorOlderData.setText(self.oldercursor)  # older plot
        self.cursorFFTRed.setText(self.redcursor)  # red FFT plot
        self.cursorFFTGreen.setText(self.greencursor)  # green FFT plot
        self.cursorFFTBlue.setText(self.bluecursor)  # blue FFT plot

        # Updating labels displaying manual RHEED oscillation calculations
        self.rheed1Label.setText(self.rheed1cal)  # update the text on the live plot
        self.rheed2Label.setText(self.rheed2cal)  # update the text on the newer plot
        self.rheed3Label.setText(self.rheed3cal)  # update the text on the older plot

        # Updating the stopwatch if it has been un-paused rather than started from 0.00
        if runstopwatch and stopwatch_active:
            self.timenow = round(float(time.time() - tstart + float(self.savedtime)), 2)  # calculating the proper time
            self.tnow = "%.2f" % self.timenow  # formatting the displayed time to 2 decimal places (e.g. 1.00)
            self.stopwatchScreen.display(self.tnow)  # display the formatted time on the stopwatch screen

        # If the stopwatch is paused, display the time at which it was paused
        if not runstopwatch and stopwatch_active:
            pausetime = '%.2f' % self.savedtime  # formatting the number to 2 decimal places
            self.stopwatchScreen.display(pausetime)  # display the formatted time on the stopwatch screen

        # Updating the timer if it is running
        if timing and timer_active:
            # If the timer is starting from the user-set value (i.e. not running after an un-pause)
            if self.savedtime2 == 0.0:
                self.remaining = (self.timerstart + float(self.totaltime)) - time.time()  # calculating remaining time
            # If the timer is resuming after a pause
            else:
                self.remaining = (self.timerstart + float(self.savedtime2)) - time.time()  # calculating remaining time
            # Performing modulo division on the remaining time (in seconds) to get hours:minutes:seconds format
            hours, rem = divmod(self.remaining, 3600)  # find number of hours remaining
            minutes, seconds = divmod(rem, 60)  # find the number of minutes remaining
            # Format the time as hh:mm:ss.xx
            self.formatted_time = str("{:0>2}:{:0>2}:{:05.2f}".format(int(hours), int(minutes), seconds))
            self.timerScreen.display(self.formatted_time)  # display the formatted time on the timer screen
            # If the timer is up
            if self.remaining < 0:
                self.timerScreen.setStyleSheet('QLCDNumber {color:red}')  # make the timer text red
                # If the timer was not started from a pause, display the amount of overtime
                if self.savedtime2 == 0.0:
                    self.overtime = time.time() - (self.timerstart + self.totaltime)
                # If the timer was started from a pause, overtime = current time - time when paused
                else:
                    self.overtime = time.time() - (self.timerstart + float(self.savedtime2))
                # Formatting the remaining time again
                hours, rem = divmod(self.overtime, 3600)
                minutes, seconds = divmod(rem, 60)
                self.formatted_overtime = str("{:0>2}:{:0>2}:{:05.2f}".format(int(hours), int(minutes), seconds))
                self.timerScreen.display(self.formatted_overtime)
        # If the timer is paused
        if not timing and timer_active:
            # Display remaining time if remaining time is > 0
            if self.remaining > 0:
                self.timerScreen.display(self.formatted_time)
            # Display the amount of overtime if remaining time is < 0
            if self.remaining < 0:
                self.timerScreen.display(self.formatted_overtime)
                self.starttimerButton.setEnabled(False)  # disable the start timer button

    # Set background image
    def setbackground(self):
        global background, backgroundset
        frame = q.get()
        img = frame["img"]
        background = img
        backgroundset = True

    # Clear background image
    def clearbackground(self):
        global background,  backgroundset
        backgroundset = False

    # Saving a single image using the "Capture" button
    def capture_image(self):
        global isfile, imnum, running, samplename, path, filename, background, backgroundset, cmap
        # This is a hacky way of splicing the camera frame image and the annotation together. The entire contents of the
        # annotation widget can be easily be grabbed as a QPixmap using the .grab() method but there is no good way to
        # directly convert to a numpy array. So, the QPixmap is saved as a .png and re-opened using PIL where it and the
        # camera frame (still as a numpy array) are pasted into a new RGB image with width equal to the camera width and
        # height equal to the sum of the camera and annotation frame heights.
        if running:
            # Sequential file naming with timestamp
            imnum_str = str(imnum).zfill(2)  # format image number as 01, 02, etc.
            timestamp = time.strftime("%Y-%m-%d %I.%M.%S %p")  # formatting timestamp
            filename = samplename+' '+imnum_str+' '+timestamp
            # Save annotation as a .png
            a = self.annotationFrame.grab()  # grab the entire annotation frame contents as a QPixmap
            a.save('annotation.png', 'png')  # save the pixmap temporarily as a .png named 'annotaiton.png'
            # Splice images
            anno = Image.open('annotation.png')  # open the saved annotation
            width1, height1 = anno.size  # get the width and height of the annotation
            self.img = self.img.convert('RGB')  # convert self.img (which is RGBA) to RGB
            width2, height2 = self.img.size  # get the width and height of the camera image
            w = width1  # total width is just the width of the camera image
            h = height1 + height2  # camera height is the sum of the camera and annotation heights
            image = Image.new('RGB', (w, h))  # create a new image with the proper dimensions
            image.paste(self.img, (0, 0))  # paste the camera image in the top of the image
            image.paste(anno, (0, height2))  # paste the annotation at the bottom of the image
            # Save completed image
            image.save(path+filename+'.png')  # save the image to the active path as a .png
            os.remove('annotation.png')  # remove the 'annotation.png' which was created temporarily
            # Increase image number by 1
            imnum = int(imnum) + 1
            # Show on the statusbar where the image was saved to and the filename it was saved as
            self.statusbar.showMessage('Image saved to '+path+' as '+filename+'.png')
        # Alert popup if you try to save an image when the camera is not running
        else:
            QtWidgets.QMessageBox.warning(self, 'Error', 'Camera is not running')

    # Saving/recording video
    def record(self):
        global recording, isfile, filename, path, samplename, vidnum, out, fourcc, vidx, vidy
        vidx, vidy = self.scaled_w, self.scaled_h
        recording = not recording
        if recording and running:
            self.statusbar.showMessage('Recording video...')
            self.recordButton.setText('Stop Recording')
            vidnum_str = str(vidnum).zfill(2)
            # Format timestamp as Year-Mo-Day Hours.Minutes.Seconds (AM/PM) i.e. 2018-10-07 03.19.23 PM
            timestamp = time.strftime("%Y-%m-%d %I.%M.%S %p")
            # Generate file name as sample name + video number + timestamp
            filename = samplename+' '+vidnum_str+' '+timestamp
            vidnum = int(vidnum) + 1  # increment the video number by 1
            # Create path if it doesn't exist so video writing doesn't fail
            if not os.path.exists(path):
                os.makedirs(path)
            # Set minimum video size to 640 by 480
            if int(vidx) < 640 and int(vidy) < 480:
                vidx, vidy = 640, 480
            # Create object that will handle the video writing. This part can be complicated depending on which computer
            # the program is running on, since not all file + codec combinations will work. The codec is determined by
            # 'fourcc' which is defined at the beginning of this code. The '.avi' extension with 'MJPG' codec seems to
            # generally work for recording color video with relatively small file sizes.
            # Arguments for cv2.VideoWriter: (filename, codec, target fps, dimensions, color (False = 8-bit grayscale))
            out = cv2.VideoWriter(path+filename+'.avi', fourcc, 35.0, (int(vidx), int(vidy)), True)
        if not recording and running:
            self.statusbar.showMessage('Video saved to '+path+' as '+filename+'.avi')
            self.recordButton.setText('Record Video')
            out.release()  # release the capture so the video can be opened on the system
        # Display an error popup if the camera is not running when the 'Record' button is clicked
        if not running:
            QtWidgets.QMessageBox.warning(self, 'Error', 'Camera is not running')

    # Live plotting intensity data ####
    def liveplot(self):
        global t0, avg1, avg2, avg3, t, oldert, olderavg1, olderavg2, olderavg3, oldt, oldavg1, oldavg2, oldavg3
        global running, liveplotting  # boolean global variables
        # Start or stop liveplotting intensity data
        liveplotting = not liveplotting
        # If the camera is running
        if running:
            # Update liveplot button and statusbar when live plotting starts; reset initial time t0 to current time
            if liveplotting:
                t0 = time.time()
                self.liveplotButton.setText('Stop Live Plot')
                self.statusbar.showMessage('Live plotting data...')
            # Update 'Newer' and 'Older' plots when live plotting is stopped
            else:
                self.liveplotButton.setText('Start Live Plot')  # update live plot button text
                self.statusbar.showMessage('Live plotting stopped')  # update status bar message text
                # TODO choose shorter names for these variables or another more streamlined way of saving data
                oldert, olderavg1, olderavg2, olderavg3 = oldt, oldavg1, oldavg2, oldavg3  # updating older data
                oldt, oldavg1, oldavg2, oldavg3 = t, avg1, avg2, avg3  # updating newer data (do this after older data)
                # Updating the 'Newer' plot, which displays the most recently collected data
                curve1 = self.plot2.plot(pen=self.redpen, clear=True)  # clear = True is so old lines are removed
                curve2 = self.plot2.plot(pen=self.greenpen)  # plot the green rectanle data using the green pen
                curve3 = self.plot2.plot(pen=self.bluepen)  # plot the blue rectangle data using the blue pen
                curve1.setData(oldt, oldavg1)  # plot data from red rectangle as red curve
                curve2.setData(oldt, oldavg2)  # plot data from green rectangle as green curve
                curve3.setData(oldt, oldavg3)  # plot data from blue rectangle as blue curve
                # Updating data on the 'Older' plot, which displays the second most recently collected data
                curve4 = self.plot3.plot(pen=self.redpen, clear=True)  # plot the red rectanle data using the red pen
                curve5 = self.plot3.plot(pen=self.greenpen)  # plot the green rectanle data using the green pen
                curve6 = self.plot3.plot(pen=self.bluepen)  # plot the blue rectanle data using the blue pen
                curve4.setData(oldert, olderavg1)  # plot data from red rectangle as red curve
                curve5.setData(oldert, olderavg2)  # plot data from green rectangle as green curve
                curve6.setData(oldert, olderavg3)  # plot data from blue rectangle as blue curve
                t, avg1, avg2, avg3 = [], [], [], []  # reset the time and intensity data so live plotting starts fresh
        # Display an error popup if the camera is not running when the 'Live Plot' button is clicked
        else:
            QtWidgets.QMessageBox.warning(self, 'Error', 'Camera is not running')

    # Show or hide shapes
    def showShapes(self):
        global drawing
        drawing = not drawing
        if drawing:
            self.drawCanvas.show()
            self.drawButton.setText('Hide Shapes')
        if not drawing:
            self.drawCanvas.hide()
            self.drawButton.setText('Show Shapes')

    # Enable or disable shape translational movement
    def moveshapes(self):
        global movingshapes
        movingshapes = not movingshapes
        if movingshapes:
            self.moveshapesButton.setText('Stop Moving')
            self.moveshapesButton.setStyleSheet('QPushButton {color:red}')
        if not movingshapes:
            self.moveshapesButton.setText('Move Shapes')
            self.moveshapesButton.setStyleSheet('QPushButton {color:black}')

    # Record position of mouse when you click a mouse button
    def mousePressEvent(self, event):
        global x1, y1, x2, y2, a1, b1, a2, b2, c1, d1, c2, d2, ic, jc, kc, xi1, xf1, xi2, xf2, xi3, xf3, l1i, l1f, i
        global red, blue, green, movingshapes

        # TODO find a way to read mouse click coordinates as relative to the camera frame instead of the main window so
        # that additional translation is not needed

        # Define x and y as position of the mouse when clicked relative to the camera frame
        # x - 10 and y - 70 translate the coordinates to the camera frame of reference, the top left corner of which is
        # 10 pixels in from the left side of the main window and 70 pixels down from the top side of the main window
        x, y = (event.pos().x() - 10), (event.pos().y() - 70)

        # TIP event.button() == 1 indicates left button; == 2 indicates right button; == 4 indicates scroll wheel
        # If the left mouse button is clicked, begin drawing shapes (drag and draw)
        if event.button() == 1:
            # Set initial point for rectangles
            if self.drawCanvas.underMouse() and movingshapes:
                self.translation = True
                self.xtrans, self.ytrans = event.pos().x(), event.pos().y()
                if red:
                    self.xl, self.yl = (x2-x1), (y2-y1)
                if green:
                    self.xl, self.yl = (x2-x1), (y2-y1)
                if blue:
                    self.xl, self.yl = (x2-x1), (y2-y1)

            if self.drawCanvas.underMouse():  # if the mouse is over the drawing canvas
                self.drawingshapes = True  # drawing shapes if the left mouse button is clicked
                self.editingshapes = False  # stop editing shapes (dragging sides) when left mouse button is clicked
                if red:  # if modifying the red rectangle
                    x1, y1 = x, y  # origin point for the red rectangle is where the mouse was clicked
                    x2, y2 = x1 + 1, y1 + 1  # specify different end position so the rectangle has nonzero dimensions
                if green:  # if modifying the green rectangle
                    a1, b1 = x, y  # origin point for the green rectangle is where the mouse was clicked
                    a2, b2 = a1 + 1, b1 + 1  # specify different end position so the rectangle has nonzero dimensions
                if blue:
                    c1, d1 = x, y  # origin point for the blue rectangle is where the mouse was clicked
                    c2, d2 = c1 + 1, d1 + 1  # specify different end position so the rectangle has nonzero dimensions

            # Update manual calculation for RHEED oscillations on newer data
            if self.plot1.underMouse():
                if ic:
                    xi1 = self.x1
                if not ic:
                    xf1 = self.x1
                    dt1 = round(((xf1 - xi1) / float(self.numpeaksLive.value())), 3)
                    df1 = round((1/dt1), 3)
                    self.rheed1cal = str(str(dt1)+' s or '+str(df1)+' Hz')
                ic = not ic

            if self.plot2.underMouse():
                if jc:
                    xi2 = self.x2
                if not jc:
                    xf2 = self.x2
                    dt2 = round(((xf2 - xi2)/float(self.numpeaksNewer.value())), 3)
                    df2 = round((1/dt2), 3)
                    self.rheed2cal = str(str(dt2)+' s or '+str(df2)+' Hz')
                jc = not jc

            if self.plot3.underMouse():
                if kc:
                    xi3 = self.x3
                if not kc:
                    xf3 = self.x3
                    dt3 = round(((xf3 - xi3)/float(self.numpeaksOlder.value())), 3)
                    df3 = round((1/dt3), 3)
                    self.rheed3cal = str(str(dt3)+' s or '+str(df3)+' Hz')
                kc = not kc

        # If the right mouse button is clicked, begin editing the shapes (changing single sides)
        if event.button() == 2:
            if self.drawCanvas.underMouse():  # if the mouse is over the drawing canvas
                self.x1o, self.y1o, self.x2o, self.y2o = x1, y1, x2, y2  # starting geometry of the red rectangle
                self.a1o, self.b1o, self.a2o, self.b2o = a1, b1, a2, b2  # starting geometry of the green rectangle
                self.c1o, self.d1o, self.c2o, self.d2o = c1, d1, c2, d2  # starting geometry of the blue rectangle
                self.startx = event.pos().x() - 10  # x position of the mouse when clicked
                self.starty = event.pos().y() - 70  # y position of the mouse when clicked
                self.editingshapes = True
                self.drawingshapes = False
                if red:
                    if 0 < x < self.x1o and self.y1o < y < self.y2o:
                        self.grow = 'left'
                    if self.x2o < x < self.scaled_w and self.y1o < y < self.y2o:
                        self.grow = 'right'
                    if 0 < y < self.y1o and self.x1o < x < self.x2o:
                        self.grow = 'up'
                    if self.y2o < y < self.scaled_h and self.x1o < x < self.x2o:
                        self.grow = 'down'
                if green:
                    if 0 < x < self.a1o and self.b1o < y < self.b2o:
                        self.grow = 'left'
                    if self.a2o < x < self.scaled_w and self.b1o < y < self.b2o:
                        self.grow = 'right'
                    if 0 < y < self.b1o and self.a1o < x < self.a2o:
                        self.grow = 'up'
                    if self.b2o < y < self.scaled_h and self.a1o < x < self.a2o:
                        self.grow = 'down'
                if blue:
                    if 0 < x < self.c1o and self.d1o < y < self.d2o:
                        self.grow = 'left'
                    if self.c2o < x < self.scaled_w and self.d1o < y < self.d2o:
                        self.grow = 'right'
                    if 0 < y < self.d1o and self.c1o < x < self.c2o:
                        self.grow = 'up'
                    if self.d2o < y < self.scaled_h and self.c1o < x < self.c2o:
                        self.grow = 'down'
        # If the scroll wheel is clicked while the mouse is over the drawing canvas, change the active rectangle color
        if (event.button() == 4, self.drawCanvas.underMouse()):
            self.selectColor()  # call the selectColor function

    # Update the rectangle as the mouse moves
    def mouseMoveEvent(self, event):
        global x1, y1, x2, y2, a1, b1, a2, b2, c1, d1, c2, d2, red, green, blue, movingshapes
        x, y = (event.pos().x() - 10), (event.pos().y() - 70)  # record the position of the mouse event (x, y)
        if not self.editingshapes and (self.drawingshapes,  # if drawing shapes and not editing them
                                       0 < x < self.scaled_w,  # if x is within the drawing frame width
                                       0 < y < self.scaled_h,  # if y is within the drawing frame height
                                       self.drawCanvas.underMouse()):  # if the mouse is over the drawing canvas
            if red:
                x2, y2 = x, y
            if green:
                a2, b2 = x, y
            if blue:
                c2, d2 = x, y

            # TODO this section still needs work; translation doesn't currently work properly
            if movingshapes and self.translation:
                if red and ((self.xtrans - x1) > x,
                            (self.scaled_w - x) > (x2 - self.xtrans),
                            (self.ytrans - y1) > y,
                            (self.scaled_h - y) > (y2 - self.ytrans)):
                        x1, y1 = x, y
                        x2, y2 = (x+self.xl), (y+self.yl)
                if green:
                    if x > (self.xtrans - a1) and y > (self.ytrans - b1):
                        a1, b1 = x, y
                if blue:
                    if x > (self.xtrans - c1) and y > (self.ytrans - d1):
                        c1, d1 = x, y

        if not self.drawingshapes and (self.editingshapes,  # if editing shapes and not drawing them
                                       0 < x < self.scaled_w,  # if x is within the drawing frame width
                                       0 < y < self.scaled_h,  # if y is within the drawing frame height
                                       self.drawCanvas.underMouse()):  # if the mouse is over the drawing canvas
            if red:  # if modifying red
                if self.grow == 'left' and not (self.x1o - (self.startx - x)) >= self.x2o:
                    x1 = self.x1o - (self.startx - x)
                if self.grow == 'right' and not (self.x2o + (x - self.startx)) <= self.x1o:
                    x2 = self.x2o + (x - self.startx)
                if self.grow == 'up' and not (self.y1o - (self.starty - y)) >= self.y2o:
                    y1 = self.y1o - (self.starty - y)
                if self.grow == 'down' and not (self.y2o + (y - self.starty)) <= self.y1o:
                    y2 = self.y2o + (y - self.starty)
            if green:  # if modifying green
                if self.grow == 'left' and not (self.a1o - (self.startx - x)) >= self.a2o:
                    a1 = self.a1o - (self.startx - x)
                if self.grow == 'right' and not (self.a2o + (x - self.startx)) <= self.a1o:
                    a2 = self.a2o + (x - self.startx)
                if self.grow == 'up' and not (self.b1o - (self.starty - y)) >= self.b2o:
                    b1 = self.b1o - (self.starty - y)
                if self.grow == 'down' and not (self.b2o + (y - self.starty)) <= self.b1o:
                    b2 = self.b2o + (y - self.starty)
            if blue:  # if modifying blue
                if self.grow == 'left' and not (self.c1o - (self.startx - x)) >= self.c2o:
                    c1 = self.c1o - (self.startx - x)
                if self.grow == 'right' and not (self.c2o + (x - self.startx)) <= self.c1o:
                    c2 = self.c2o + (x - self.startx)
                if self.grow == 'up' and not (self.d1o - (self.starty - y)) >= self.d2o:
                    d1 = self.d1o - (self.starty - y)
                if self.grow == 'down' and not (self.d2o + (y - self.starty)) <= self.d1o:
                    d2 = self.d2o + (y - self.starty)

    # Record position of mouse when you release the button
    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        global x1, y1, x2, y2, a1, b1, a2, b2, c1, d1, c2, d2, red, blue, green
        x, y = (event.pos().x() - 10), (event.pos().y() - 70)
        if event.button() == 1:
            if not self.editingshapes and (self.drawingshapes,  # if drawing shapes and not editing them
                                           0 < x < self.scaled_w,  # x is within the drawing frame width
                                           0 < y < self.scaled_h,  # y is within the drawing frame height
                                           self.drawCanvas.underMouse()):  # if mouse is over the drawing canvas
                if red:
                    x2, y2 = x, y
                if green:
                    a2, b2 = x, y
                if blue:
                    c2, d2 = x, y
        if event.button() == 2:  # event.button() == 2 indicates the right mouse button
            if not self.drawingshapes and (self.editingshapes,  # if editing shapes and not drawing them
                                           0 < x < self.scaled_w,  # x is within the drawing frame width
                                           0 < y < self.scaled_h,  # y is within the drawing frame height
                                           self.drawCanvas.underMouse()):  # if mouse is over the drawing canvas
                # TODO comment this section of code
                if red:
                    if self.grow == 'left' and not (self.x1o - (self.startx - x)) >= self.x2o:
                        x1 = self.x1o - (self.startx - x)
                    if self.grow == 'right' and not (self.x2o + (x - self.startx)) <= self.x1o:
                        x2 = self.x2o + (x - self.startx)
                    if self.grow == 'up' and not (self.y1o - (self.starty - y)) >= self.y2o:
                        y1 = self.y1o - (self.starty - y)
                    if self.grow == 'down' and not (self.y2o + (y - self.starty)) <= self.y1o:
                        y2 = self.y2o + (y - self.starty)
                if green:
                    if self.grow == 'left' and not (self.a1o - (self.startx - x)) >= self.a2o:
                        a1 = self.a1o - (self.startx - x)
                    if self.grow == 'right' and not (self.a2o + (x - self.startx)) <= self.a1o:
                        a2 = self.a2o + (x - self.startx)
                    if self.grow == 'up' and not (self.b1o - (self.starty - y)) >= self.b2o:
                        b1 = self.b1o - (self.starty - y)
                    if self.grow == 'down' and not (self.b2o + (y - self.starty)) <= self.b1o:
                        b2 = self.b2o + (y - self.starty)
                if blue:
                    if self.grow == 'left' and not (self.c1o - (self.startx - x)) >= self.c2o:
                        c1 = self.c1o - (self.startx - x)
                    if self.grow == 'right' and not (self.c2o + (x - self.startx)) <= self.c1o:
                        c2 = self.c2o + (x - self.startx)
                    if self.grow == 'up' and not (self.d1o - (self.starty - y)) >= self.d2o:
                        d1 = self.d1o - (self.starty - y)
                    if self.grow == 'down' and not (self.d2o + (y - self.starty)) <= self.d1o:
                        d2 = self.d2o + (y - self.starty)
        self.grow = ''
        self.drawingshapes = False
        self.editingshapes = False
        self.translation = False

    # Change which rectangle color you're editing
    def selectColor(self):
        global red, green, blue, i
        i += 1
        if i == 4:
            i = 1
        if i == 1:
            self.rectButton.setStyleSheet('QPushButton {color: red}')
            self.rectButton.setText('Editing Red')
            red, green, blue = True, False, False
        if i == 2:
            self.rectButton.setStyleSheet('QPushButton {color: green}')
            self.rectButton.setText('Editing Green')
            red, green, blue = False, True, False
        if i == 3:
            self.rectButton.setStyleSheet('QPushButton {color: blue}')
            self.rectButton.setText('Editing Blue')
            red, green, blue = False, False, True

    # Plot FFT of most recent data
    def plotFFT(self):
        global oldt, oldavg1, oldavg2, oldavg3
        # Plot FFT of data from red rectangle
        t_length = len(oldt)
        dt = (max(oldt) - min(oldt))/(t_length-1)
        red_no_dc = oldavg1 - np.mean(oldavg1)
        yf1 = rfft(red_no_dc)
        tf = np.linspace(0.0, 1.0/(2.0*dt), t_length//2)
        i = np.argmax(abs(yf1[0:t_length//2]))
        redpeak = tf[i]
        peakfind1 = str('Peak at '+str(round(redpeak, 2))+' Hz or '+str(round(1/redpeak, 2))+' s')
        self.redpeakLabel.setText(peakfind1)
        pen1 = pg.mkPen('r', width=1, style=QtCore.Qt.SolidLine)
        self.plotFFTred.plot(tf, np.abs(yf1[0:t_length//2]), pen=pen1, clear=True)
        # Plot FFT of data from green rectangle
        green_no_dc = oldavg2 - np.mean(oldavg2)
        yf2 = rfft(green_no_dc)
        j = np.argmax(abs(yf2[0:t_length//2]))
        greenpeak = tf[j]
        peakfind2 = str('Peak at '+str(round(greenpeak, 2))+' Hz or '+str(round(1/greenpeak, 2))+' s')
        self.greenpeakLabel.setText(peakfind2)
        pen2 = pg.mkPen('g', width=1, style=QtCore.Qt.SolidLine)
        self.plotFFTgreen.plot(tf, np.abs(yf2[0:t_length//2]), pen=pen2, clear=True)
        # Plot FFT of data from blue rectangle
        blue_no_dc = oldavg3 - np.mean(oldavg3)
        yf3 = rfft(blue_no_dc)
        k = np.argmax(abs(yf3[0:t_length//2]))
        bluepeak = tf[k]
        peakfind3 = str('Peak at '+str(round(bluepeak, 2))+' Hz or '+str(round(1/bluepeak, 2))+' s')
        self.bluepeakLabel.setText(peakfind3)
        pen3 = pg.mkPen('b', width=1, style=QtCore.Qt.SolidLine)
        self.plotFFTblue.plot(tf, np.abs(yf3[0:t_length//2]), pen=pen3, clear=True)
        # Show labels for peak positions
        self.redpeakLabel.show()
        self.greenpeakLabel.show()
        self.bluepeakLabel.show()

    # Change sample
    def changeSample(self):
        global samplename, grower, path, imnum, vidnum, isfile, basepath
        samplename, ok = QtWidgets.QInputDialog.getText(w, 'Change sample name', 'Enter sample name: ')
        if ok:
            isfile = True
            imnum, vidnum = 1, 1
            self.sampleLabel.setText('Current Sample: '+samplename)
            path = str(basepath+grower+'/'+samplename+'/')
            # Create folder to save images in if it doesn't already exist
            if not os.path.exists(path):
                os.makedirs(path)

    # Change grower
    def changeGrower(self):
        global samplename, grower, path, imnum, vidnum, basepath
        grower, ok = QtWidgets.QInputDialog.getText(w, 'Change grower', 'Who is growing? ')
        if ok:
            imnum, vidnum = 1, 1
            self.growerLabel.setText('Current Grower: '+grower)
            path = str(basepath+grower+'/'+samplename+'/')
            # Create folder to save images in if it doesn't already exist
            if not os.path.exists(path):
                os.makedirs(path)

    # Open the current save directory
    def openDirectory(self):
        global path
        p = os.path.realpath(path)
        os.startfile(p)  # startfile only works on windows

    # Saving notes
    def saveNotes(self):
        global path, filename
        timestamp = time.strftime("%Y-%m-%d %I.%M.%S %p")  # formatting timestamp
        if not os.path.exists(path):
            os.makedirs(path)
        with open(path+'Growth notes '+timestamp+'.txt', 'w+') as file:
            file.write(str(self.noteEntry.toPlainText()))
        self.statusbar.showMessage('Notes saved to '+path+' as '+'Growth notes '+timestamp+'.txt')

    # Clearing notes
    def clearNotes(self):
        reply = QtGui.QMessageBox.question(w, 'Caution', 'Are you sure you want to clear all growth notes?',
                                           QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)  # default buttons: 'Yes' & 'No'
        if reply == QtGui.QMessageBox.Yes:
            self.noteEntry.clear()
        if reply == QtGui.QMessageBox.No:
            pass

    # Set colormaps
    def mapGray(self):
        global cmap
        cmap = cm.gist_gray

    def mapGreen(self):
        global cmap
        cmap = FRHEEDcmap

    def mapHot(self):
        global cmap
        cmap = cm.seismic

    def mapPlasma(self):
        global cmap
        cmap = cm.plasma

    # Image inversion
    def invert(self):
        global inverted
        inverted = not inverted

    # Mouse tracking on live plot
    def mouseMoved1(self, evt):
        mousePoint1 = self.plot1.plotItem.vb.mapSceneToView(evt[0])
        self.x1 = round(mousePoint1.x(), 3)
        self.y1 = round(mousePoint1.y(), 3)
        self.livecursor = str('x = '+str(self.x1)+', y = '+str(self.y1))

    # Mouse tracking on newer plot
    def mouseMoved2(self, evt):
        mousePoint2 = self.plot2.plotItem.vb.mapSceneToView(evt[0])
        self.x2 = round(mousePoint2.x(), 3)
        self.y2 = round(mousePoint2.y(), 3)
        self.newercursor = str('x = '+str(self.x2)+', y = '+str(self.y2))

    # Mouse tracking on older plot
    def mouseMoved3(self, evt):
        mousePoint3 = self.plot3.plotItem.vb.mapSceneToView(evt[0])
        self.x3 = round(mousePoint3.x(), 3)
        self.y3 = round(mousePoint3.y(), 3)
        self.oldercursor = str('x = '+str(self.x3)+', y = '+str(self.y3))

    # Mouse tracking on red FFT plot
    def mouseMoved4(self, evt):
        mousePoint4 = self.plotFFTred.plotItem.vb.mapSceneToView(evt[0])
        self.x4 = round(mousePoint4.x(), 3)
        self.y4 = round(mousePoint4.y(), 3)
        self.redcursor = str('x = '+str(self.x4)+', y = '+str(self.y4))

    # Mouse tracking on green FFT plot
    def mouseMoved5(self, evt):
        mousePoint5 = self.plotFFTgreen.plotItem.vb.mapSceneToView(evt[0])
        self.x5 = round(mousePoint5.x(), 3)
        self.y5 = round(mousePoint5.y(), 3)
        self.greencursor = str('x = '+str(self.x5)+', y = '+str(self.y5))

    # Mouse tracking on blue FFT plot
    def mouseMoved6(self, evt):
        mousePoint6 = self.plotFFTblue.plotItem.vb.mapSceneToView(evt[0])
        self.x6 = round(mousePoint6.x(), 3)
        self.y6 = round(mousePoint6.y(), 3)
        self.bluecursor = str('x = '+str(self.x6)+', y = '+str(self.y6))

    # Start or stop stopwatch
    def stopwatch(self):
        global runstopwatch, tstart, stopwatch_active
        stopwatch_active = True
        runstopwatch = not runstopwatch
        if runstopwatch:
            tstart = time.time()
            self.startstopwatchButton.setText('Stop')
            self.startstopwatchButton.setStyleSheet('QPushButton {color:red}')
        if not runstopwatch:
            self.startstopwatchButton.setText('Start')
            self.startstopwatchButton.setStyleSheet('QPushButton {color:green}')
            self.savedtime = self.timenow

    # Clear the stopwatch (reset to 0.00)
    def clearstopwatch(self):
        global runstopwatch, stopwatch_active
        if not runstopwatch:
            self.savedtime, self.timenow = 0, 0
            self.stopwatchScreen.display('%.2f') % self.savedtime
            stopwatch_active = False

    # Change the set time for the timer, i.e. what it counts down from
    def changetime(self):
        if not timing:
            self.starttimerButton.setText('Start')
            self.starttimerButton.setStyleSheet('QPushButton {color:green}')
        self.hours = self.setHours.value()
        self.hr = str(self.hours).zfill(2)
        self.minutes = self.setMinutes.value()
        self.minu = str(self.minutes).zfill(2)
        self.seconds = self.setSeconds.value()
        self.sec = str(self.seconds).zfill(2)
        self.start_time = str(self.hr+':'+self.minu+':'+self.sec+'.00')
        self.timerScreen.display(self.start_time)

    # Start or pause timer
    def timer(self):
        global timing, timer_active
        timer_active = True  # set the timer to active (determines whether the buttons should say 'Start' or 'Resume')
        timing = not timing  # start/stop the timer (this is what controls whether or not the numbers are updating)
        # Starting the timer
        if timing:
            self.timerstart = time.time()  # record the time when the timer was started/resumed
            self.starttimerButton.setText('Pause')  # set the timer button text to 'Pause')
            self.starttimerButton.setStyleSheet('QPushButton {color:black}')  # make the timer button text color black
            self.timerScreen.setStyleSheet('QLCDNumber {color:black}')  # make timer font color black
            # Calculate the total timer duration in seconds
            self.totaltime = self.hours*60*60 + self.minutes*60 + self.seconds
            # Display the user-selected timer amount on the timer screen
            self.start_time = str(self.hr+':'+self.minu+':'+self.sec+'.00')  # format hr:min:sec.xx
        # Pausing the timer
        if not timing:
            self.starttimerButton.setText('Resume')  # set the timer button text to 'Resume'
            self.starttimerButton.setStyleSheet('QPushButton {color:green}')  # make the timer button text green
            if self.remaining > 0:
                self.savedtime2 = self.remaining  # update the saved time to however much time is remaining on the timer
                self.timerScreen.display(self.formatted_time)  # display the remaining time when the timer was paused
            else:
                self.starttimerButton.setEnabled(False)
                self.starttimerButton.setText('Time\'s up')
                self.starttimerButton.setStyleSheet('QPushButton {color:red}')

    # Reset the timer back to the starting time
    def resettimer(self):
        global timing, timer_active
        timing = False  # reset the timer (not starting from paused state)
        timer_active = False  # stop the timer
        self.savedtime2 = 0.0  # reset saved time to 0 (essentially the time elapsed since the timer button was clicked)
        self.timerScreen.setStyleSheet('QLCDNumber {color:black}')  # make the timer font color black
        self.timerScreen.display(self.start_time)  # display the starting time (e.g. 2:00:00 or whatever the user sets)
        self.starttimerButton.setEnabled(True)  # re-enable the start timer button
        self.starttimerButton.setText('Start')  # set the timer button text to 'Start'
        self.starttimerButton.setStyleSheet('QPushButton {color:green}')  # make the timer button text color green

    # Close the program and terminate threads
    def closeEvent(self, event):
        global running, cam, grower, samplename, config, camtype, out, q
        # Update grower and sample name config options before quitting
        config['Default']['grower'] = str(grower)
        config['Default']['sample'] = str(samplename)
        with open('config.ini', 'w') as configfile:
            config.write(configfile)
        running = False  # stop grabbing camera frames
        time.sleep(0.1)  # give the program time to close threads
        print('Shutting down...')
        # Release the FLIR camera
        if camtype == 'FLIR':
            cam.EndAcquisition()
            cam.DeInit()
            del cam
            cam_list.Clear()
        # Release the USB camera
        if camtype == 'USB':
            cam = cv2.VideoCapture(0)
            cam.release()
            print('Released camera...')
        # Release video capturing
        out.release()
        # TODO ensure program closes down and terminates threads correctly
        # Clean up the threads
        q.terminate()
        # Release FLIR instance
        if camtype == 'FLIR':
            system.ReleaseInstance()
        time.sleep(0.2)
        self.close()


# if __name__ == '__main__': ensures that the code executes when run directly, but not when called by another program
if __name__ == '__main__':
    fps = 35.0  # this isn't actually used but if I take it out things don't work and I don't know why
    capture_thread = threading.Thread(target=grab, args=(fps, q))  # again, fps isn't actually used but leave it alone

    # Run the program, show the main window and name it 'FRHEED'
    app = QtWidgets.QApplication(sys.argv)  # run the app with the command line arguments (sys.argv) passed to it

    # This is where the main window is actually created and shown
    w = FRHEED(None)
    w.setWindowTitle('FRHEED')
    w.show()
    app.exec_()

# TODO
"""
- shape translational motion
- figure out why spacebar triggers buttons
- add 1D line plot for strain analysis
- fix memory pileup
- 3D plotting
- arbitrary masks
- advanced camera settings (gamma, white balance)
"""
