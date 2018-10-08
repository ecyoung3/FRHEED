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
import PySpin
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
grower = "None"
samplenum = "None"
imnum = 1
vidnum = 1
background = []
exposure = float(9000.0)# value in microseconds
avg = 0
t0 = time.time()
t, avg1, avg2, avg3, oldt, oldavg1, oldavg2, oldavg3, oldert, olderavg1, olderavg2, olderavg3 = [], [], [], [], [], [], [], [], [], [], [], []
x1, y1, x2, y2 = 0, 0, 640, 480
a1, b1, a2, b2 = 0, 0, 640, 480
c1, d1, c2, d2 = 0, 0, 640, 480
i = 1
ic, jc, kc = True, True, True
red, green, blue = True, False, False
path = 'C:/Users/Palmstrom Lab/Desktop/FRHEED/'
filename = 'default'
#### Define colormap ####
cmp = Colormap()
FRHEEDcmap = cmp.cmap_linear('black', 'green', 'white')
cm.register_cmap(name='RHEEDgreen', cmap = FRHEEDcmap)
cmap = FRHEEDcmap
#cmp.test_colormap(FRHEEDcmap)
#### Loading UI file from qt designer ####
form_class = uic.loadUiType("FRHEED.ui")[0]
#### Define "shortcut" for queue ####
q = queue.Queue()
#### Define video recording codec ####
fourcc = cv2.VideoWriter_fourcc(*'XVID')
#### Set default appearance of plots ####
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 0.0)
#### Initialize configuration file ####
config = configparser.ConfigParser()
config.read('config.ini')
#### Connect to RHEED camera ####
system = PySpin.System.GetInstance()
cam_list = system.GetCameras()
cam = cam_list.GetBySerial("18434385")
nodemap_tldevice = cam.GetTLDeviceNodeMap()
cam.Init()
cam.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
cam.ExposureTime.SetValue(exposure) # exposure time in microseconds
time.sleep(0.01)
nodemap = cam.GetNodeMap()
node_acquisition_mode = PySpin.CEnumerationPtr(nodemap.GetNode("AcquisitionMode"))
node_acquisition_mode_continuous = node_acquisition_mode.GetEntryByName("Continuous")
acquisition_mode_continuous = node_acquisition_mode_continuous.GetValue()
node_acquisition_mode.SetIntValue(acquisition_mode_continuous)
cam.BeginAcquisition()  

#### Code for grabbing frames from camera in threaded loop ####
def grab(width, height, fps, queue):
    global grower, running, recording, path, filename, exposure, isfile, samplenum, vidnum, out, fourcc, setout, cam, scaled_w, scaled_h, inverted
    while running:
        frame = {}        
        image_result = cam.GetNextImage()
        img = image_result.GetNDArray()
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
        self.setupUi(self)
        #### Setting menu actions ####
        self.connectButton.clicked.connect(self.connectCamera)
        self.menuExit.triggered.connect(self.closeEvent)
        self.captureButton.clicked.connect(self.capture_image)
        self.recordButton.clicked.connect(self.record)
        self.liveplotButton.clicked.connect(self.liveplot)
        self.drawButton.clicked.connect(self.showShapes)
        self.changeExposure.valueChanged.connect(self.setExposure)
        self.changeExposureTime.valueChanged.connect(self.setExposureTime)
        self.lowexposureButton.clicked.connect(self.lowexposure)
        self.highexposureButton.clicked.connect(self.highexposure)
        self.highexposuretime = int(config['Exposure']['highexposure'])
        self.lowexposuretime = int(config['Exposure']['lowexposure'])
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
        global running, grower, isfile, samplenum, path, imnum, vidnum, growerset
        if not growerset:
            grower, ok = QtWidgets.QInputDialog.getText(w, 'Enter grower', 'Who is growing? ')
            if ok:
                imnum, vidnum = 1, 1
                growerset = True
                path = str('C:/Users/Palmstrom Lab/Desktop/FRHEED/'+grower+'/')
            else:
                QtWidgets.QMessageBox.warning(self, 'Error', 'Grower not set')
                return
        if not isfile:  
            samplenum, ok = QtWidgets.QInputDialog.getText(w, 'Change sample name', 'Enter sample name: ')
            if ok:
                imnum, vidnum = 1, 1
                isfile = True
                path = str('C:/Users/Palmstrom Lab/Desktop/FRHEED/'+grower+'/'+samplenum+'/')
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
        cam.ExposureTime.SetValue(exposure)
        
    #### Set exposure time ####
    def setExposureTime(self):
        global exposure, cam
        expotime = self.changeExposureTime.value()
        exposure = float(expotime * 1000)
        cam.ExposureTime.SetValue(exposure)
    
    #### Preset high exposure for taking images ####
    def highexposure(self):
        global exposure, cam
        val = str(1000*self.setHighExposure.value())
        config['Exposure']['highexposure'] = val
        self.highexposuretime = config['Exposure']['highexposure']
        cam.ExposureTime.SetValue(int(self.highexposuretime))
        
    #### Preset low exposure for taking RHEED oscillations ####
    def lowexposure(self):
        global exposure, cam
        val = str(1000*self.setLowExposure.value())
        config['Exposure']['lowexposure'] = val
        self.lowexposuretime = config['Exposure']['lowexposure']
        cam.ExposureTime.SetValue(int(self.lowexposuretime))
        
    #### Protocol for updating the video frames in the GUI ####
    def update_frame(self):
        global avg1, avg2, avg3, t0, t, p, x1, y1, x2, y2, a1, b1, a2, b2, c1, d1, c2, d2, inverted, tstart, samplenum, grower, sampletextset, cmap, background, backgroundset, scaled_w, scaled_h, runstopwatch, timing, timer_active, stopwatch_active
        #### Size and identity of camera frame ####
        self.window_width = self.parentFrame.frameSize().width()
        self.window_height = self.parentFrame.frameSize().height()
        if not q.empty():
            self.connectButton.setText('Connected')
            frame = q.get()
            img = frame["img"]
            if inverted:
                img = np.invert(img)
            if backgroundset:
                img = img - background
#            img = np.flipud(img)
            img_height, img_width = img.shape
            #### Scaling the image from the camera ####
            scale_w = float(self.window_width) / float(img_width)
            scale_h = float(self.window_height) / float(img_height)
            scale = min([scale_w, scale_h])
            if scale == 0:
                scale = 1
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
            #### Updating live data ####
            if liveplotting:
                avg_1 = img[y1:y2, x1:x2].mean()
                avg_1 = round(avg_1, 3)
                avg_2 = img[b1:b2, a1:a2].mean()
                avg_2 = round(avg_2, 3)
                avg_3 = img[d1:d2, c1:c2].mean()
                avg_3 = round(avg_3, 3)
                avg1.append(avg_1)
                avg2.append(avg_2)
                avg3.append(avg_3)
                timenow = time.time() - t0
                t.append(timenow)
                pen1 = pg.mkPen('r', width=1, style=QtCore.Qt.SolidLine)
                pen2 = pg.mkPen('g', width=1, style=QtCore.Qt.SolidLine)
                pen3 = pg.mkPen('b', width=1, style=QtCore.Qt.SolidLine)
                curve1 = self.plot1.plot(pen=pen1, clear = True)
                curve2 = self.plot1.plot(pen=pen2)
                curve3 = self.plot1.plot(pen=pen3)
                curve1.setData(t, avg1)
                curve2.setData(t, avg2)
                curve3.setData(t, avg3)
            if drawing:
                pixmap = QtGui.QPixmap(self.drawCanvas.frameGeometry().width(), self.drawCanvas.frameGeometry().height())
                pixmap.fill(QtGui.QColor("transparent"))
                qp = QtGui.QPainter(pixmap)
                qp.setPen(QtGui.QPen(QtCore.Qt.red, 2, QtCore.Qt.SolidLine))
                qp.drawRect(x1, y1, x2 - x1, y2 - y1)
                qp.setPen(QtGui.QPen(QtCore.Qt.green, 2, QtCore.Qt.SolidLine))
                qp.drawRect(a1, b1, a2 - a1, b2 - b1)
                qp.setPen(QtGui.QPen(QtCore.Qt.blue, 2, QtCore.Qt.SolidLine))
                qp.drawRect(c1, d1, c2 - c1, d2 - d1)
                qp.end()
                self.drawCanvas.setPixmap(pixmap)
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
                self.overtime =  time.time() - (self.timerstart + float(self.savedtime2))
                hours, rem = divmod(self.overtime, 3600)
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
            print(self.scaled_w, self.scaled_h)
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
            if liveplotting:
                self.liveplotButton.setText('Stop Live Plot')
                t0 = time.time()
                self.statusbar.showMessage('Live plotting data...')
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
            
    #### Record position of mouse when you click the button ####        
    def mousePressEvent(self, event: QtGui.QMouseEvent):
        global x1, y1, x2, y2, a1, b1, a2, b2, c1, d1, c2, d2, red, blue, yellow, ic, jc, kc, xi1, xf1, xi2, xf2, xi3, xf3, l1i, l1f
        if self.drawCanvas.underMouse():
            if red:
                x1, y1 = event.pos().x()-10, event.pos().y()-70
            if green:
                a1, b1 = event.pos().x()-10, event.pos().y()-70
            if blue:
                c1, d1 = event.pos().x()-10, event.pos().y()-70
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

    #### Record position of mouse when you release the button ####    
    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        global x1, y1, x2, y2, a1, b1, a2, b2, c1, d1, c2, d2, red, blue, green
        if self.drawCanvas.underMouse():
            if red:
                x2, y2 = event.pos().x()-10, event.pos().y()-70
            if green:
                a2, b2 = event.pos().x()-10, event.pos().y()-70
            if blue:
                c2, d2 = event.pos().x()-10, event.pos().y()-70
                
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
        global samplenum, grower, path, imnum, vidnum, isfile
        samplenum, ok = QtWidgets.QInputDialog.getText(w, 'Change sample name', 'Enter sample name: ')
        if ok:
            isfile = True
            imnum, vidnum = 1, 1
            self.sampleLabel.setText('Current Sample: '+samplenum)
            path = str('C:/Users/Palmstrom Lab/Desktop/FRHEED/'+grower+'/'+samplenum+'/')
            #### Create folder to save images in if it doesn't already exist ####
            if not os.path.exists(path):
                os.makedirs(path)
                print(path+' created')
                
    #### Change grower ####
    def changeGrower(self):
        global samplenum, grower, path, imnum, vidnum, growerset
        grower, ok = QtWidgets.QInputDialog.getText(w, 'Change grower', 'Who is growing? ')
        if ok:
            growerset = True
            imnum, vidnum = 1, 1
            self.growerLabel.setText('Current Grower: '+grower)
            path = str('C:/Users/Palmstrom Lab/Desktop/FRHEED/'+grower+'/'+samplenum+'/')
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
        cam.EndAcquisition()
        cam.DeInit()
        del cam
        cam_list.Clear()
        system.ReleaseInstance()
        self.close()
        capture_thread.terminate()

#### Initialize threading with arguments for camera source, queue, frame dimensions and FPS ####
capture_thread = threading.Thread(target=grab, args = (2048, 1536, 35, q)) # RHEED camera is 2048 by 1536

#### Run the program, show the main window and name it 'FRHEED' ####
app = QtWidgets.QApplication(sys.argv)
w = FRHEED(None)
w.setWindowTitle('FRHEED')
w.show()
app.exec_()

#### TODO: ####
"""
- make rectangles resize with rest of window
- add 1D line plot for strain analysis
- fix bugs associated with startup crashes
- figure out source of background noise in image
- debug timer/stopwatch
"""
