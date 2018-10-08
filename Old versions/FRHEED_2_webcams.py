from PyQt5 import QtCore, QtGui, uic, QtWidgets
import sys
import cv2
import numpy as np
import threading
import time
import queue
import os
import pyqtgraph as pg
from scipy.fftpack import rfft
from PIL import Image, ImageQt
#import PySpin
from matplotlib import cm
from colormap import Colormap
import configparser

#### Define global variables ####
running = False
capture_thread = None
isfile = False
recording = False
setout = False
liveplotting = False
drawing = False
fileselected = False
sampletextset = False
growerset = False
backgroundset = False
runstopwatch = False
stopwatch_active = False
timer_active = False
timing = False
inverted = False
movingshapes = False
averaging = False
summing = True
grower = "None"
samplenum = "None"
imnum = 1
vidnum = 1
background = []
#exposure = float(100000)# value in microseconds
exposure = -5
avg = 0
t0 = time.time()
t, avg1, avg2, avg3, oldt, oldavg1, oldavg2, oldavg3, oldert, olderavg1, olderavg2, olderavg3 = [], [], [], [], [], [], [], [], [], [], [], []

#### Default dimensions of rectangles: 640x480 centered in upper left corner (0,0) ####
x1, y1, x2, y2 = 0, 0, 640, 480
a1, b1, a2, b2 = 0, 0, 640, 480
c1, d1, c2, d2 = 0, 0, 640, 480
basecoords = x1, x2, y1, y2, a1, a2, b1, b2, c1, c2, d1, d2
i = 1 # Index for which color rectangle is currently active: 1 = red, 2 = green, 3 = blue
red, green, blue = True, False, False # Red is the active rectangle

#### Enable manual calculation for RHEED peaks ####
ic = kc = jc = True

#### Default filename if nothing is selected ####
filename = 'default'

#### Loading UI file from qt designer ####
form_class = uic.loadUiType("FRHEED.ui")[0] # file should be located in same directory as this script

#### Define "shortcut" for queue ####
q = queue.Queue()

#### Define video recording codec ####
fourcc = cv2.VideoWriter_fourcc(*'XVID') # unsure which combination of codec/file extension works 

#### Set default appearance of plots ####
pg.setConfigOption('background', 'w') # 'w' = white background
pg.setConfigOption('foreground', 0.0) # black axes lines and labels

#### Initialize configuration file ####
config = configparser.ConfigParser()
config.read('config.ini')

#### Set save location if none set ####
if config['Default']['pathset'] == 'False':
    warning = QtWidgets.QMessageBox.warning(None, 'Notice', 'Please select a base directory for saving files.')
    file = str(QtWidgets.QFileDialog.getExistingDirectory(None, 'Select Save Directory'))
    config['Default']['pathset'] = 'True'
    config['Default']['path'] = str(file+'/')
    with open('config.ini', 'w') as configfile:
        config.write(configfile)

#### Config options ####
basepath = config['Default']['path']
#### Create basepath if it doesn't exist for some reason ####
if not os.path.exists(basepath):
    os.makedirs(basepath)
    
#### Set colormap to config default ####
cmap = config['Default']['cmap']

#### Define colormap ####
cmp = Colormap()
FRHEEDcmap = cmp.cmap_linear('black', 'green', 'white') # create custom colormapfrom black -> white with linear green gradient
cm.register_cmap(name='RHEEDgreen', cmap = FRHEEDcmap) # registerthe custom cmap as a matplotlib cmap
cmap = cm.get_cmap(name=cmap) # convert config cmap to the matplotlib format

##### Connect to RHEED camera ####
#system = PySpin.System.GetInstance() # start new instance
#cam_list = system.GetCameras() # get list of cameras
#cam = cam_list.GetBySerial("18434385") # get the specific camera for VG RHEED
#nodemap_tldevice = cam.GetTLDeviceNodeMap() # need to figure out what this does
#cam.Init() # initialize camera
#cam.ExposureAuto.SetValue(PySpin.ExposureAuto_Off) # turn off auto exposure
#cam.ExposureTime.SetValue(exposure) # set exposure time in microseconds
#time.sleep(0.01) # wait for things to initialize
#nodemap = cam.GetNodeMap() # I think this is getting a list of camera options/functions 
#node_acquisition_mode = PySpin.CEnumerationPtr(nodemap.GetNode("AcquisitionMode")) # this and the next 3 lines set up continuous acquisition for streaming
#node_acquisition_mode_continuous = node_acquisition_mode.GetEntryByName("Continuous")
#acquisition_mode_continuous = node_acquisition_mode_continuous.GetValue()
#node_acquisition_mode.SetIntValue(acquisition_mode_continuous)
#cam.BeginAcquisition() # begin acquiring data from the camera

cam = cv2.VideoCapture(0) # grab frames from webcam in slot 0
cam.set(cv2.CAP_PROP_EXPOSURE, exposure) # set exposure

#### Code for grabbing frames from camera in threaded loop ####
def grab(width, height, fps, queue):
    global grower, running, recording, path, filename, exposure, isfile, samplenum, vidnum, out, fourcc, setout, cam, scaled_w, scaled_h, inverted, cam
    while running:
        frame = {}   
#        image_result = cam.GetNextImage() # get image from FLIR GigE camera buffer
#        img = image_result.GetNDArray() # grab image as a numpy array
        grabbed, img = cam.read() # read frame from webcam; grabbed = True if the frame isn't empty
        if grabbed:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) # convert webcam to grayscale
        frame["img"] = img
        if queue.qsize() < 50:
            queue.put(frame)
            if recording:
                if not setout:
                    time.sleep(0.5)
                    setout = True
                img = cv2.resize(img, dsize=(int(scaled_w), int(scaled_h)), interpolation=cv2.INTER_CUBIC)
                if inverted:
                    img = np.invert(img)
                imc = np.uint8(cmap(img)*255)
                imc = Image.fromarray(imc)
                imc.show()
                out.write(imc)

#### Programming main window ####
class FRHEED(QtWidgets.QMainWindow, form_class):
    global config
    def __init__(self, parent=None):
        global samplenum, exposure, x1, y1, x2, y2, grower
        QtWidgets.QMainWindow.__init__(self, parent)
        self.buttons = QtWidgets.qApp.mouseButtons()
        self.drawingshapes = False
        self.setupUi(self)
        self.oldwidth = self.parentFrame.frameSize().width()
        self.oldheight = self.parentFrame.frameSize().height()
        #### Setting menu actions ####
        self.connectButton.clicked.connect(self.connectCamera)
        self.menuExit.triggered.connect(self.closeEvent)
        self.captureButton.clicked.connect(self.capture_image)
        self.recordButton.clicked.connect(self.record)
        self.liveplotButton.clicked.connect(self.liveplot)
        self.drawButton.clicked.connect(self.showShapes)
        self.moveshapesButton.clicked.connect(self.moveshapes)
        self.changeExposure.valueChanged.connect(self.setExposure)
        self.changeExposureTime.valueChanged.connect(self.setExposureTime)
        self.lowexposureButton.clicked.connect(self.lowexposure)
        self.highexposureButton.clicked.connect(self.highexposure)
        self.highexposuretime = int(config['Default']['highexposure'])
        self.lowexposuretime = int(config['Default']['lowexposure'])
        self.rectButton.clicked.connect(self.selectColor)
        self.rectButton.setStyleSheet('QPushButton {color:red}')
        self.annotateLayer.setStyleSheet('QLabel {color:white}')
        self.annotateMisc.setStyleSheet('QLabel {color:white}')
        self.annotateOrientation.setStyleSheet('QLabel {color:white}')
        self.annotateSampleName.setStyleSheet('QLabel {color:white}')
        self.fftButton.clicked.connect(self.plotFFT)
        self.growerButton.clicked.connect(self.changeGrower)
        self.sampleButton.clicked.connect(self.changeSample)
        self.savenotesButton.clicked.connect(self.saveNotes)
        self.clearnotesButton.clicked.connect(self.clearNotes)
        self.redpeakLabel.hide()
        self.greenpeakLabel.hide()
        self.bluepeakLabel.hide()
        self.grayscaleButton.clicked.connect(self.mapGray)
        self.grayscaleSample.setPixmap(QtGui.QPixmap('gray colormap.png'))
        self.greenButton.clicked.connect(self.mapGreen)
        self.greenSample.setPixmap(QtGui.QPixmap('green colormap.png'))
        self.hotButton.clicked.connect(self.mapHot)
        self.hotSample.setPixmap(QtGui.QPixmap('hot colormap.png'))
        self.plasmaButton.clicked.connect(self.mapPlasma)
        self.backgroundButton.clicked.connect(self.setbackground)
        self.clearbackgroundButton.clicked.connect(self.clearbackground)
        self.plasmaSample.setPixmap(QtGui.QPixmap('plasma colormap.png'))
        self.invertButton.clicked.connect(self.invert)
        p = self.annotationFrame.palette()
        p.setColor(self.annotationFrame.backgroundRole(), QtCore.Qt.black)
        self.annotationFrame.setPalette(p)
        self.starttimerButton.setStyleSheet('QPushButton {color:green}')
        self.startstopwatchButton.setStyleSheet('QPushButton {color:green}')
        self.timerScreen.display('00:00:00:00')
        self.starttimerButton.clicked.connect(self.timer)
        self.resettimerButton.clicked.connect(self.resettimer)
        self.startstopwatchButton.clicked.connect(self.stopwatch)
        self.resetstopwatchButton.clicked.connect(self.clearstopwatch)
        self.setHours.valueChanged.connect(self.changetime)
        self.setMinutes.valueChanged.connect(self.changetime)
        self.setSeconds.valueChanged.connect(self.changetime)
        self.timeset = 0.0
        self.savedtime = 0.0
        self.savedtime2 = 0.0
        self.livecursor = ''
        self.newercursor = ''
        self.oldercursor = ''
        self.redcursor = ''
        self.greencursor = ''
        self.bluecursor = ''
        self.rheed1cal = ''
        self.rheed2cal = ''
        self.rheed3cal = ''
        #### Create window for live data plotting ####
        self.plot1.showGrid(True, True)
        self.plot1.setContentsMargins(0,4,10,0)
        self.plot1.setLimits(xMin=0)
        self.plot1.setLabel('bottom', 'Time (s)')
        self.proxy1 = pg.SignalProxy(self.plot1.scene().sigMouseMoved, rateLimit=60, slot=self.mouseMoved1)
        self.proxy2 = pg.SignalProxy(self.plot2.scene().sigMouseMoved, rateLimit=60, slot=self.mouseMoved2)
        self.proxy3 = pg.SignalProxy(self.plot3.scene().sigMouseMoved, rateLimit=60, slot=self.mouseMoved3)
        self.proxy4 = pg.SignalProxy(self.plotFFTred.scene().sigMouseMoved, rateLimit=60, slot=self.mouseMoved4)
        self.proxy5 = pg.SignalProxy(self.plotFFTgreen.scene().sigMouseMoved, rateLimit=60, slot=self.mouseMoved5)
        self.proxy6 = pg.SignalProxy(self.plotFFTblue.scene().sigMouseMoved, rateLimit=60, slot=self.mouseMoved6)
        self.plot2.plotItem.showGrid(True, True)
        self.plot2.plotItem.setContentsMargins(0,4,10,0)
        self.plot2.setLimits(xMin=0)
        self.plot2.setLabel('bottom', 'Time (s)')
        self.plot3.plotItem.showGrid(True, True)
        self.plot3.plotItem.setContentsMargins(0,4,10,0)
        self.plot3.setLimits(xMin=0)
        self.plot3.setLabel('bottom', 'Time (s)')
        #### Create window for FFT plot ####
        self.plotFFTred.plotItem.showGrid(True, True)
        self.plotFFTred.plotItem.setContentsMargins(0,4,10,0)
        self.plotFFTred.setLabel('bottom', 'Frequency (Hz)')
        self.plotFFTgreen.plotItem.showGrid(True, True)
        self.plotFFTgreen.plotItem.setContentsMargins(0,4,10,0)
        self.plotFFTgreen.setLabel('bottom', 'Frequency (Hz)')
        self.plotFFTblue.plotItem.showGrid(True, True)
        self.plotFFTblue.plotItem.setContentsMargins(0,4,10,0)
        self.plotFFTblue.setLabel('bottom', 'Frequency (Hz)')
        #### Set 1 second timer before connecting to camera ####
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(1) #time in milliseconds
        
    #### Start grabbing camera frames when Camera -> Connect is clicked ####
    def connectCamera(self):
        global running, grower, isfile, samplenum, path, imnum, vidnum, growerset, basepath
        if not growerset:
            grower, ok = QtWidgets.QInputDialog.getText(w, 'Enter grower', 'Who is growing? ')
            if ok:
                imnum, vidnum = 1, 1
                growerset = True
                path = str(basepath+grower+'/')
                if not os.path.exists(path):
                    os.makedirs(path)
            else:
                QtWidgets.QMessageBox.warning(self, 'Error', 'Grower not set')
                return
        if not isfile:  
            samplenum, ok = QtWidgets.QInputDialog.getText(w, 'Change sample name', 'Enter sample name: ')
            if ok:
                imnum, vidnum = 1, 1
                isfile = True
                path = str(basepath+grower+'/'+samplenum+'/')
                #### Create folder to save images in if it doesn't already exist ####
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
        
    #### Change camera exposure ####
    def setExposure(self):
        global exposure, cam
        expo = self.changeExposure.value()
        exposure = float(1.2**expo) # Exponential scale for exposure (time in microseconds)
        self.changeExposureTime.setValue(int(exposure / 1000.0))
#        cam.ExposureTime.SetValue(exposure)
        cam.set(cv2.CAP_PROP_EXPOSURE, exposure) # setting webcam exposure
        
    #### Set exposure time ####
    def setExposureTime(self):
        global exposure, cam
        expotime = self.changeExposureTime.value()
        exposure = float(expotime * 1000)
#        cam.ExposureTime.SetValue(exposure)
        cam.set(cv2.CAP_PROP_EXPOSURE, exposure)

    
    #### Preset high exposure for taking images ####
    def highexposure(self):
        global exposure, cam
        val = str(1000*self.setHighExposure.value())
        #### Update the high exposure default in the config file ####
        config['Defaault']['highexposure'] = val
        with open('config.ini', 'w') as configfile:
            config.write(configfile)
        self.highexposuretime = config['Default']['highexposure']
#        cam.ExposureTime.SetValue(int(self.highexposuretime))
        cam.set(cv2.CAP_PROP_EXPOSURE, exposure)
        
    #### Preset low exposure for taking RHEED oscillations ####
    def lowexposure(self):
        global exposure, cam
        val = str(1000*self.setLowExposure.value())
        #### Update the high exposure default in the config file ####
        config['Default']['lowexposure'] = val
        with open('config.ini', 'w') as configfile:
            config.write(configfile)
        self.lowexposuretime = config['Default']['lowexposure']
#        cam.ExposureTime.SetValue(int(self.lowexposuretime))
        cam.set(cv2.CAP_PROP_EXPOSURE, exposure)
        
    #### Protocol for updating the video frames in the GUI ####
    def update_frame(self):
        global avg1, avg2, avg3, t0, t, p, x1, y1, x2, y2, a1, b1, a2, b2, c1, d1, c2, d2, averaging, summing, movingshapes, basecoords, inverted, tstart, samplenum, grower, sampletextset, cmap, background, backgroundset, scaled_w, scaled_h, runstopwatch, timing, timer_active, stopwatch_active
        #### Size and identity of camera frame ####
        self.window_width = self.parentFrame.frameSize().width()
        self.window_height = self.parentFrame.frameSize().height()
        if not q.empty():
            if self.drawingshapes:
                basecoords = x1, x2, y1, y2, a1, a2, b1, b2, c1, c2, d1, d2
            self.connectButton.setText('Connected')
            frame = q.get()
            img = frame["img"]
            if inverted:
                img = np.invert(img)
            if backgroundset:
                img = img - background
#            img = np.flipud(img)
            img_height, img_width = img.shape[0], img.shape[1]
            #### Scaling the image from the camera ####
            scale_w = float(self.window_width) / float(img_width)
            scale_h = float(self.window_height) / float(img_height)
            scale = min([scale_w, scale_h])
            self.scaled_w = int(scale * img_width)
            self.scaled_h = int(scale * img_height)
            scaled_w, scaled_h = self.scaled_w, self.scaled_h
            #### Resize camera canvas to proper size ####
            self.cameraCanvas.resize(self.scaled_w, self.scaled_h)
            self.drawCanvas.resize(self.scaled_w, self.scaled_h)
            #### Resize annotation frame to proper width ####
            self.annotationFrame.resize(self.scaled_w, self.annotationFrame.frameSize().height())
            img = cv2.resize(img, dsize=(self.scaled_w, self.scaled_h), interpolation=cv2.INTER_CUBIC)
            #### Apply colormap ####
            imc = Image.fromarray(np.uint8(cmap(img)*255)) # colormaps: cm.gray, FRHEEDcmap, cm.Greens
            #### Convert PIL image to QImage
            imc = ImageQt.ImageQt(imc)
            #### Adding the camera to the screen ####
            self.cameraCanvas.setPixmap(QtGui.QPixmap.fromImage(imc))
            #### Resize rectangles with window ####
            if self.oldwidth != self.window_width or self.oldheight != self.window_height:
                newcoords = list(map(lambda x: int(x*scale), basecoords))
                x1, x2, y1, y2, a1, a2, b1, b2, c1, c2, d1, d2 = newcoords
            #### Updating live data ####
            if liveplotting:
                #### This section sorts coordinates such that x1 < x2 so taking the mean doesn't return a null value ####
                c = [(x1, x2), (y1, y2), (a1, a2), (b1, b2), (c1, c2), (d1, d2)]
                k = []
                #### Sort each pair such that the first value is always the smaller of the two ####
                for i in range(len(c)):
                    j = sorted(c[i])
                    k.append(j)
                #### If the values in a pair are equal, add 1 to the second value so taking the mean is still valid ####
                for i in range(len(k)):
                    if k[i][0] == k[i][1]:
                        k[i][1] = k[i][0] + 1
                #### Update the values to take the mean of ####
                [(x1a, x2a), (y1a, y2a), (a1a, a2a), (b1a, b2a), (c1a, c2a), (d1a, d2a)] = k
                #### Take the averages of the defined area ####
                if averaging:
                    avg_1 = img[y1a:y2a, x1a:x2a].mean()
                    avg_1 = round(avg_1, 3) # round to 3 decimal places
                    avg_2 = img[b1a:b2a, a1a:a2a].mean()
                    avg_2 = round(avg_2, 3)
                    avg_3 = img[d1a:d2a, c1a:c2a].mean()
                    avg_3 = round(avg_3, 3)
                if summing:
                    avg_1 = img[y1a:y2a, x1a:x2a].sum()
                    avg_1 = round(avg_1, 3) # round to 3 decimal places
                    avg_2 = img[b1a:b2a, a1a:a2a].sum()
                    avg_2 = round(avg_2, 3)
                    avg_3 = img[d1a:d2a, c1a:c2a].sum()
                    avg_3 = round(avg_3, 3)
                avg1.append(avg_1) # append data for live plotting
                avg2.append(avg_2)
                avg3.append(avg_3)
                timenow = time.time() - t0 # update current time
                t.append(timenow) # append current time to time data
                pen1 = pg.mkPen('r', width=1, style=QtCore.Qt.SolidLine) # plot first line with red pen, 'r'
                pen2 = pg.mkPen('g', width=1, style=QtCore.Qt.SolidLine) # plot first line with green pen, 'g'
                pen3 = pg.mkPen('b', width=1, style=QtCore.Qt.SolidLine) # plot first line with blue pen, 'b'
                curve1 = self.plot1.plot(pen=pen1, clear = True) # clear = True to make plotting faster. only do this for the first plot otherwise not all plots will appear
                curve2 = self.plot1.plot(pen=pen2)
                curve3 = self.plot1.plot(pen=pen3)
                #### Updating the data for each curve
                curve1.setData(t, avg1)
                curve2.setData(t, avg2)
                curve3.setData(t, avg3)
            if drawing:
                pixmap = QtGui.QPixmap(self.drawCanvas.frameGeometry().width(), self.drawCanvas.frameGeometry().height())
                pixmap.fill(QtGui.QColor("transparent"))
                qp = QtGui.QPainter(pixmap)
                qp.setPen(QtGui.QPen(QtCore.Qt.red, 1, QtCore.Qt.SolidLine))
                self.redrect = qp.drawRect(x1, y1, x2 - x1, y2 - y1)
                qp.setPen(QtGui.QPen(QtCore.Qt.green, 1, QtCore.Qt.SolidLine))
                self.greenrect = qp.drawRect(a1, b1, a2 - a1, b2 - b1)
                qp.setPen(QtGui.QPen(QtCore.Qt.blue, 1, QtCore.Qt.SolidLine))
                self.bluerect = qp.drawRect(c1, d1, c2 - c1, d2 - d1)
                qp.end()
                self.drawCanvas.setPixmap(pixmap)
            self.oldwidth = self.window_width
            self.oldheight = self.window_height
            self.relativescale = scale
        self.sampleLabel.setText('Current Sample: '+samplenum)
        self.growerLabel.setText('Current Grower: '+grower)
        self.annotateSampleName.setText('Sample: '+self.setSampleName.text())
        self.annotateOrientation.setText('Orientation: '+self.setOrientation.text())
        self.annotateLayer.setText('Growth layer: '+self.setGrowthLayer.text())
        self.annotateMisc.setText('Other notes: '+self.setMisc.text())
        #### Updating cursor position text labels ####
        self.cursorLiveData.setText(self.livecursor)
        self.cursorNewerData.setText(self.newercursor)
        self.cursorOlderData.setText(self.oldercursor)
        self.cursorFFTRed.setText(self.redcursor)
        self.cursorFFTGreen.setText(self.greencursor)
        self.cursorFFTBlue.setText(self.bluecursor)
        #### Updating manual RHEED oscillation calculations ####
        self.rheed1Label.setText(self.rheed1cal)
        self.rheed2Label.setText(self.rheed2cal)
        self.rheed3Label.setText(self.rheed3cal)
        if runstopwatch and stopwatch_active:
            self.timenow = round(float(time.time() - tstart + float(self.savedtime)), 2)
            self.tnow = "%.2f" % self.timenow
            self.stopwatchScreen.display(self.tnow)
        if not runstopwatch and stopwatch_active:
            _ = '%.2f' % self.savedtime
            self.stopwatchScreen.display(_)
        if timing and timer_active:
            if self.savedtime2 == 0.0:
                self.remaining = (self.timerstart + float(self.totaltime)) - time.time()
            else:
                self.remaining = (self.timerstart + float(self.savedtime2)) - time.time()
            hours, rem = divmod(self.remaining, 3600)
            minutes, seconds = divmod(rem, 60)
            self.formatted_time = str("{:0>2}:{:0>2}:{:05.2f}".format(int(hours),int(minutes),seconds))
            self.timerScreen.display(self.formatted_time)
            if self.remaining < 0:
                self.timerScreen.setStyleSheet('QLCDNumber {color:red}')
                if self.savedtime2 == 0.0:
                    self.remaining = (self.timerstart + float(self.totaltime)) - time.time()
                else:
                    self.remaining = (self.timerstart + float(self.savedtime2)) - time.time()
                hours, rem = divmod(self.remaining, 3600)
                minutes, seconds = divmod(rem, 60)
                self.formatted_time = str("{:0>2}:{:0>2}:{:05.2f}".format(int(hours),int(minutes),seconds))
                self.timerScreen.display(self.formatted_time)
                self.remaining = self.overtime
        if not timing and timer_active:
            hours, rem = divmod(self.remaining, 3600)
            minutes, seconds = divmod(rem, 60)
            self.formatted_time = str("{:0>2}:{:0>2}:{:05.2f}".format(int(hours),int(minutes),seconds))
            self.timerScreen.display(self.formatted_time)
        if self.numpeaksLive.value() < 3 or self.numpeaksNewer.value() < 3 or self.numpeaksOlder.value() < 3:
            QtWidgets.QMessageBox.warning(self, 'Alert', 'Your calibration is shit.')
            self.numpeaksLive.setValue(10)
            self.numpeaksNewer.setValue(10)
            self.numpeaksOlder.setValue(10)
        if not sampletextset and samplenum != "None":
            self.setSampleName.setText(samplenum)
            sampletextset = True
    #### Set background image ####
    def setbackground(self):
        global background, backgroundset
        frame = q.get()
        img = frame["img"]
        background = img
        backgroundset = True

    #### Clear background image ####
    def clearbackground(self):
        global background,  backgroundset
        backgroundset = False
        
    #### Saving a single image using the "Capture" button ####            
    def capture_image(self):
        global isfile, imnum, running, samplenum, path, filename, background, backgroundset, cmap
        if running:
            frame = q.get()
            img = frame["img"]
            if inverted:
                img = np.invert(img)
            if backgroundset:
                img = img - background
            img = cv2.resize(img, dsize=(int(self.scaled_w), int(self.scaled_h)), interpolation=cv2.INTER_CUBIC)
            imc = Image.fromarray(np.uint8(cmap(img)*255)) # colormaps: cm.gray, FRHEEDcmap, cm.Greens
            #### Sequential file naming with timestamp ####
            imnum_str = str(imnum).zfill(2) # format image number as 01, 02, etc.
            timestamp = time.strftime("%Y-%m-%d %I.%M.%S %p") # formatting timestamp
            filename = samplenum+' '+imnum_str+' '+timestamp
            #### Save annotation ####
            a = self.annotationFrame.grab()
            a.save('annotation.png', 'png')
            #### Actually saving the file
            imc.save('picture.png', 'png')
            #### Splice images ####
            anno = Image.open('annotation.png')
            width1, height1 = anno.size
            pic = Image.open('picture.png')
            width2, height2 = pic.size
            w = width1
            h = height1 + height2
            image = Image.new('RGB', (w, h))
            image.paste(pic, (0,0))
            image.paste(anno, (0,height2))
            #### Save completed image ####
            image.save(path+filename+'.png')
            os.remove('annotation.png')
            os.remove('picture.png')
            #### Increase image number by 1 ####
            imnum = int(imnum) + 1
            self.statusbar.showMessage('Image saved to '+path+' as '+filename+'.png')
        #### Alert popup if you try to save an image when the camera is not running ####
        else:
            QtWidgets.QMessageBox.warning(self, 'Error', 'Camera is not running')
    
    #### Saving/recording video ####        
    def record(self):
        global recording, isfile, filename, path, samplenum, vidnum, out, fourcc
        recording = not recording
        if recording and running:
            self.statusbar.showMessage('Recording video...')
            self.recordButton.setText('Stop Recording')
            vidnum_str = str(vidnum).zfill(2)
            timestamp = time.strftime("%Y-%m-%d %I.%M.%S %p") # formatting timestamp
            filename = samplenum+' '+vidnum_str+' '+timestamp            
            vidnum = int(vidnum) + 1
            out = cv2.VideoWriter(path+filename+'.mp4', fourcc, 35.0, (int(self.scaled_w), int(self.scaled_h)), True)
        if not recording and running:
            self.statusbar.showMessage('Video saved to '+path+' as '+filename+'.mp4')
            self.recordButton.setText('Record Video')
        if not running:
            QtWidgets.QMessageBox.warning(self, 'Error', 'Camera is not running')
            
    #### Live plotting intensity data ####
    def liveplot(self):
        global running, liveplotting, t0, avg1, avg2, avg3, t, oldert, olderavg1, olderavg2, olderavg3, oldt, oldavg1, oldavg2, oldavg3
        liveplotting = not liveplotting
        if running:
            #### Update button and statusbar when live plotting starts; reset initial time t0 ####
            if liveplotting:
                self.liveplotButton.setText('Stop Live Plot')
                t0 = time.time()
                self.statusbar.showMessage('Live plotting data...')
            #### Update 'Newer' and 'Older' plots when live plotting is stopped ####
            else:
                self.liveplotButton.setText('Start Live Plot')
                self.statusbar.showMessage('Live plotting stopped')
                oldert = oldt
                olderavg1 = oldavg1
                olderavg2 = oldavg2
                olderavg3 = oldavg3
                oldt = t
                oldavg1 = avg1
                oldavg2 = avg2
                oldavg3 = avg3
                pen1 = pg.mkPen('r', width=1, style=QtCore.Qt.SolidLine)
                pen2 = pg.mkPen('g', width=1, style=QtCore.Qt.SolidLine)
                pen3 = pg.mkPen('b', width=1, style=QtCore.Qt.SolidLine)
                curve1 = self.plot2.plot(pen=pen1, clear = True)
                curve2 = self.plot2.plot(pen=pen2)
                curve3 = self.plot2.plot(pen=pen3)
                curve1.setData(oldt, oldavg1)
                curve2.setData(oldt, oldavg2)
                curve3.setData(oldt, oldavg3)
                curve4 = self.plot3.plot(pen=pen1, clear = True)
                curve5 = self.plot3.plot(pen=pen2)
                curve6 = self.plot3.plot(pen=pen3)
                curve4.setData(oldert, olderavg1)
                curve5.setData(oldert, olderavg2)
                curve6.setData(oldert, olderavg3)
                t = []
                avg1 = []
                avg2 = []
                avg3 = []
        else:
            QtWidgets.QMessageBox.warning(self, 'Error', 'Camera is not running')
            
    #### Show or hide shapes ####
    def showShapes(self):
        global drawing
        drawing = not drawing
        if drawing:
            self.drawCanvas.show()
            self.drawButton.setText('Hide Shapes')
        if not drawing:
            self.drawCanvas.hide()
            self.drawButton.setText('Show Shapes')
            
    #### Enable or disable shape translational movement ####
    def moveshapes(self):
        global movingshapes
        movingshapes = not movingshapes
        if movingshapes:
            self.moveshapesButton.setText('Stop Moving')
            self.moveshapesButton.setStyleSheet('QPushButton {color:red}')
        if not movingshapes:
            self.moveshapesButton.setText('Move Shapes')
            self.moveshapesButton.setStyleSheet('QPushButton {color:black}')
            
    #### Record position of mouse when you click the button ####        
    def mousePressEvent(self, event):
        global x1, y1, x2, y2, a1, b1, a2, b2, c1, d1, c2, d2, red, blue, green, ic, jc, kc, xi1, xf1, xi2, xf2, xi3, xf3, l1i, l1f, i, movingshapes
        x, y = (event.pos().x() - 10), (event.pos().y() - 70)
        if event.button() == 1:
            #### Set initial point for rectangles ####
            if self.drawCanvas.underMouse() and movingshapes:
                self.translation = True
                self.xtrans, self.ytrans = event.pos().x(), event.pos().y()
                if red:
                    self.xl, self.yl = (x2-x1), (y2-y1)
                if green:
                    self.xl, self.yl = (x2-x1), (y2-y1)
                if blue:
                    self.xl, self.yl = (x2-x1), (y2-y1)
                    
            if self.drawCanvas.underMouse(): # mouse must be over the camera frame; left mouse click to draw
                self.drawingshapes = True
                self.editingshapes = False
                if red:
                    x1, y1 = x, y
                    x2, y2 = x1 - 1, y1 - 1
                if green:
                    a1, b1 = x, y
                    a2, b2 = a1 - 1, b1 - 1
                if blue:
                    c1, d1 = x, y
                    c2, d2 = c1 - 1, d1 - 1
            #### Update manual calculation for RHEED oscillations on newer data ####
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
                
        if event.button() == 2:
            if self.drawCanvas.underMouse():
                self.x1o, self.y1o, self.x2o, self.y2o, self.a1o, self.b1o, self.a2o, self.b2o, self.c1o, self.d1o, self.c2o, self.d2o = x1, y1, x2, y2, a1, b1, a2, b2, c1, d1, c2, d2
                self.startx = event.pos().x() - 10
                self.starty = event.pos().y() - 70
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
                        
        if event.button() == 4:
            if self.drawCanvas.underMouse():
                self.selectColor()
                    
    #### Update the rectangle as the mouse moves ####       
    def mouseMoveEvent(self, event):
        global x1, y1, x2, y2, a1, b1, a2, b2, c1, d1, c2, d2, red, green, blue, movingshapes
        x, y = (event.pos().x() - 10), (event.pos().y() - 70)
        if self.drawCanvas.underMouse() and 0 < x < self.scaled_w and 0 < y < self.scaled_h:
            if not self.editingshapes and self.drawingshapes:
                if red:
                    x2, y2 = x, y
                if green:
                    a2, b2 = x, y
                if blue:
                    c2, d2 = x, y 
                    
            if movingshapes and self.translation:
                if red:
                    if (self.xtrans - x1) > x and (self.scaled_w - x) > (x2 - self.xtrans) and (self.ytrans - y1) > y and (self.scaled_h - y) > (y2 - self.ytrans):
                        x1, y1 = x, y
                        x2, y2 = (x+self.xl), (y+self.yl)
                if green:
                    if x > (self.xtrans - a1) and y > (self.ytrans - b1):
                        a1, b1 = x, y
                if blue:
                    if x > (self.xtrans - c1) and y > (self.ytrans - d1):
                        c1, d1 = x, y
                    
        if self.drawCanvas.underMouse() and 0 < x < self.scaled_w and 0 < y < self.scaled_h and self.editingshapes and not self.drawingshapes:
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
            
    #### Record position of mouse when you release the button ####    
    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        global x1, y1, x2, y2, a1, b1, a2, b2, c1, d1, c2, d2, red, blue, green
        x, y = (event.pos().x() - 10), (event.pos().y() - 70)
        if event.button() == 1:
            if self.drawCanvas.underMouse() and 0 < x < self.scaled_w and 0 < y < self.scaled_h and self.drawingshapes and not self.editingshapes:
                if red:
                    x2, y2 = x, y
                if green:
                    a2, b2 = x, y
                if blue:
                    c2, d2 = x, y
        if event.button() == 2:
            if self.drawCanvas.underMouse() and 0 < x < self.scaled_w and 0 < y < self.scaled_h and not self.drawingshapes and self.editingshapes:
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
        
    #### Change which rectangle color you're editing ####            
    def selectColor(self):
        global red, green, blue, i
        i +=1
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
            
    #### Plot FFT of most recent data ####
    def plotFFT(self):
        global fileselected, oldt, oldavg1, oldavg2, oldavg3
        if not fileselected:
            #### Plot FFT of data from red rectangle ####
            t_length = len(oldt)
            dt = (max(oldt) - min(oldt))/(t_length-1)
            red_no_dc = oldavg1 - np.mean(oldavg1)
            yf1 = rfft(red_no_dc)
            tf = np.linspace(0.0, 1.0/(2.0*dt), t_length//2)
            i = np.argmax(abs(yf1[0:t_length//2]))
            redpeak = tf[i]
            peakfind1=str('Peak at '+str(round(redpeak, 2))+' Hz or '+str(round(1/redpeak, 2))+' s')
            self.redpeakLabel.setText(peakfind1)
            pen1 = pg.mkPen('r', width=1, style=QtCore.Qt.SolidLine)
            self.plotFFTred.plot(tf, np.abs(yf1[0:t_length//2]), pen=pen1, clear = True)
            #### Plot FFT of data from green rectangle ####
            green_no_dc = oldavg2 - np.mean(oldavg2)
            yf2 = rfft(green_no_dc)
            j = np.argmax(abs(yf2[0:t_length//2]))
            greenpeak = tf[j]
            peakfind2=str('Peak at '+str(round(greenpeak, 2))+' Hz or '+str(round(1/greenpeak, 2))+' s')
            self.greenpeakLabel.setText(peakfind2)
            pen2 = pg.mkPen('g', width=1, style=QtCore.Qt.SolidLine)
            self.plotFFTgreen.plot(tf, np.abs(yf2[0:t_length//2]), pen=pen2, clear = True)
            #### Plot FFT of data from blue rectangle ####
            blue_no_dc = oldavg3 - np.mean(oldavg3)
            yf3 = rfft(blue_no_dc)
            k = np.argmax(abs(yf3[0:t_length//2]))
            bluepeak = tf[k]
            peakfind3=str('Peak at '+str(round(bluepeak, 2))+' Hz or '+str(round(1/bluepeak, 2))+' s')
            self.bluepeakLabel.setText(peakfind3)
            pen3 = pg.mkPen('b', width=1, style=QtCore.Qt.SolidLine)
            self.plotFFTblue.plot(tf, np.abs(yf3[0:t_length//2]), pen=pen3, clear = True) 
            #### Show labels for peak positions ####
            self.redpeakLabel.show()
            self.greenpeakLabel.show()
            self.bluepeakLabel.show()
            
    #### Change sample ####
    def changeSample(self):
        global samplenum, grower, path, imnum, vidnum, isfile, basepath
        samplenum, ok = QtWidgets.QInputDialog.getText(w, 'Change sample name', 'Enter sample name: ')
        if ok:
            isfile = True
            imnum, vidnum = 1, 1
            self.sampleLabel.setText('Current Sample: '+samplenum)
            path = str(basepath+grower+'/'+samplenum+'/')
            #### Create folder to save images in if it doesn't already exist ####
            if not os.path.exists(path):
                os.makedirs(path)
                print(path+' created')
                
    #### Change grower ####
    def changeGrower(self):
        global samplenum, grower, path, imnum, vidnum, growerset, basepath
        grower, ok = QtWidgets.QInputDialog.getText(w, 'Change grower', 'Who is growing? ')
        if ok:
            growerset = True
            imnum, vidnum = 1, 1
            self.growerLabel.setText('Current Grower: '+grower)
            path = str(basepath+grower+'/'+samplenum+'/')
            #### Create folder to save images in if it doesn't already exist ####
            if not os.path.exists(path):
                os.makedirs(path)
                    
    #### Saving notes ####
    def saveNotes(self):
        global path, filename
        timestamp = time.strftime("%Y-%m-%d %I.%M.%S %p") # formatting timestamp
        if not os.path.exists(path):
            os.makedirs(path)
        with open(path+'Growth notes '+timestamp+'.txt', 'w+') as file:
            file.write(str(self.noteEntry.toPlainText()))
        self.statusbar.showMessage('Notes saved to '+path+' as '+'Growth notes '+timestamp+'.txt')
        
    #### Clearing notes ####
    def clearNotes(self):
        reply = QtGui.QMessageBox.question(w, 'Caution', 'Are you sure you want to clear all growth notes?', QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)
        if reply == QtGui.QMessageBox.Yes:
            self.noteEntry.clear()
        if reply == QtGui.QMessageBox.No:
            pass
        
    #### Set colormaps ####
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
        
    #### Image inversion ####
    def invert(self):
        global inverted
        inverted = not inverted
        
    #### Mouse tracking on live plot ####
    def mouseMoved1(self, evt):
        mousePoint1 = self.plot1.plotItem.vb.mapSceneToView(evt[0])
        self.x1 = round(mousePoint1.x(), 3)
        self.y1 = round(mousePoint1.y(), 3)
        self.livecursor = str('x = '+str(self.x1)+', y = '+str(self.y1))
        
    #### Mouse tracking on newer plot ####
    def mouseMoved2(self, evt):
        mousePoint2 = self.plot2.plotItem.vb.mapSceneToView(evt[0])
        self.x2 = round(mousePoint2.x(), 3)
        self.y2 = round(mousePoint2.y(), 3)
        self.newercursor = str('x = '+str(self.x2)+', y = '+str(self.y2))
        
    #### Mouse tracking on older plot ####
    def mouseMoved3(self, evt):
        mousePoint3 = self.plot3.plotItem.vb.mapSceneToView(evt[0])
        self.x3 = round(mousePoint3.x(), 3)
        self.y3 = round(mousePoint3.y(), 3)
        self.oldercursor = str('x = '+str(self.x3)+', y = '+str(self.y3))
        
    #### Mouse tracking on red FFT plot ####
    def mouseMoved4(self, evt):
        mousePoint4 = self.plotFFTred.plotItem.vb.mapSceneToView(evt[0])
        self.x4 = round(mousePoint4.x(), 3)
        self.y4 = round(mousePoint4.y(), 3)
        self.redcursor = str('x = '+str(self.x4)+', y = '+str(self.y4))
        
    #### Mouse tracking on green FFT plot ####
    def mouseMoved5(self, evt):
        mousePoint5 = self.plotFFTgreen.plotItem.vb.mapSceneToView(evt[0])
        self.x5 = round(mousePoint5.x(), 3)
        self.y5 = round(mousePoint5.y(), 3)
        self.greencursor = str('x = '+str(self.x5)+', y = '+str(self.y5))
    
    #### Mouse tracking on blue FFT plot ####
    def mouseMoved6(self, evt):
        mousePoint6 = self.plotFFTblue.plotItem.vb.mapSceneToView(evt[0])
        self.x6 = round(mousePoint6.x(), 3)
        self.y6 = round(mousePoint6.y(), 3)
        self.bluecursor = str('x = '+str(self.x6)+', y = '+str(self.y6))
        
    #### Start or stop stopwatch ####
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
        
    #### Clear stopwatch ####         
    def clearstopwatch(self):
        global runstopwatch, stopwatch_active
        if not runstopwatch:
            self.savedtime, self.timenow = 0, 0
            self.stopwatchScreen.display('%.2f') % self.savedtime
            stopwatch_active = False

    #### Start or pause timer ####  
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
        
    def timer(self):
        global timing, timer_active
        timer_active = True
        timing = not timing
        if timing:
            self.timerScreen.setStyleSheet('QLCDNumber {color:black}')
            self.timerstart = time.time()
            self.starttimerButton.setText('Pause')
            self.starttimerButton.setStyleSheet('QPushButton {color:black}')
            self.totaltime = self.hours*60*60 + self.minutes*60 + self.seconds
            self.start_time = str(self.hr+':'+self.minu+':'+self.sec+'.00')
        if not timing:
            self.starttimerButton.setStyleSheet('QPushButton {color:green}')
            self.starttimerButton.setText('Resume')
            self.savedtime2 = self.remaining
            self.timerScreen.display(self.savedtime2)
        
    #### Reset timer ####    
    def resettimer(self):
        global timing, timer_active
        timing = False
        timer_active = False
        self.savedtime2 = 0.0
        self.timerScreen.setStyleSheet('QLCDNumber {color:black}')
        self.timerScreen.display(self.start_time)
        self.starttimerButton.setText('Start')
        self.starttimerButton.setStyleSheet('QPushButton {color:green}')

    #### Close the program and terminate threads ####            
    def closeEvent(self, event):
        global running, cam
        running = False
        print('Shutting down...')
#        cam.EndAcquisition()
#        cam.DeInit()
#        del cam
#        cam_list.Clear()
        cam.release()        
#        capture_thread.terminate()
#        system.ReleaseInstance()
        self.close()


if __name__ == '__main__':
    #### Initialize threading with arguments for camera source, queue, frame dimensions and FPS ####
    camera_width = int(config['Default']['width'])
    camera_height = int(config['Default']['height'])
    fps = int(config['Default']['fps'])
    capture_thread = threading.Thread(target=grab, args = (camera_width, camera_height, fps, q))
    #### Run the program, show the main window and name it 'FRHEED' ####
    app = QtWidgets.QApplication(sys.argv)
    #### Load in app icons of all sizes ####
    w = FRHEED(None)
    w.setWindowTitle('FRHEED')
    w.show()
    app.exec_()

#### TODO: ####
"""
- shape translational motion
- figure out why spacebar triggers button pyqt
- add 1D line plot for strain analysis
- fix bugs associated with startup crashes
- figure out source of background noise in image
- debug timer/stopwatch (proper time when timer passes 0)
- fix memory pileup
"""
