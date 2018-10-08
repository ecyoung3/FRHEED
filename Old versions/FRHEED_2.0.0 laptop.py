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
from PIL import Image

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
grower = "None"
samplenum = "None"
imnum = 1
vidnum = 1
exposure = -5
avg = 0
t0 = time.time()
t, avg1, avg2, avg3, oldt, oldavg1, oldavg2, oldavg3, oldert, olderavg1, olderavg2, olderavg3 = [], [], [], [], [], [], [], [], [], [], [], []
x1, y1, x2, y2 = 0, 0, 640, 480
a1, b1, a2, b2 = 0, 0, 640, 480
c1, d1, c2, d2 = 0, 0, 640, 480
i = 1
red, green, blue = True, False, False
path = 'C:/Users/ellio/Desktop/FRHEED/Default/'
filename = 'default'
#### Loading UI file from qt designer ####
form_class = uic.loadUiType("FRHEED.ui")[0]
#### Define "shortcut" for queue ####
q = queue.Queue()
#### Define video recording codec ####
fourcc = cv2.VideoWriter_fourcc(*'MP4V')
#### Set default appearance of plots ####
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 0.0)

#### Code for grabbing frames from camera in threaded loop ####
def grab(cam, queue, width, height, fps):
    global grower, running, recording, path, filename, exposure, isfile, samplenum, vidnum, out, fourcc, setout
    capture = cv2.VideoCapture(cam)
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    capture.set(cv2.CAP_PROP_FPS, fps)
    if grower == "None":
        grower, ok = QtWidgets.QInputDialog.getText(w, 'Enter grower', 'Who is growing? ')
    if not isfile:
        samplenum, ok = QtWidgets.QInputDialog.getText(w, 'Enter sample name', 'Enter sample name: ')
        if ok:
            isfile = True
            print('it worked')
            path = str('C:/Users/ellio/Desktop/FRHEED/'+grower+'/'+samplenum+'/')
            #### Create folder to save images in if it doesn't already exist ####
            if not os.path.exists(path):
                os.makedirs(path)
    while running:
        frame = {}        
        capture.grab()
        retval, img = capture.retrieve(0)
        frame["img"] = img
        print(type(img))
        capture.set(cv2.CAP_PROP_EXPOSURE, exposure)
        if queue.qsize() < 30:
            queue.put(frame)
            if recording:
                if not setout:
                    time.sleep(0.5)
                    setout = True
                out.write(img)
        else:
            print(queue.qsize())

#### Display frames grabbed from camera ####
class Camera(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(Camera, self).__init__(parent)
        self.image = None

    def setImage(self, image):
        self.image = image
        sz = image.size()
        self.setMinimumSize(sz)
        self.update()

    def paintEvent(self, event):
        qp = QtGui.QPainter()
        qp.begin(self)
        if self.image:
            qp.drawImage(QtCore.QPoint(0, 0), self.image)
        qp.end()

#### Programming main window ####
class FRHEED(QtWidgets.QMainWindow, form_class):
    def __init__(self, parent=None):
        global samplenum, exposure, x1, y1, x2, y2, grower
        QtWidgets.QMainWindow.__init__(self, parent)
        self.setupUi(self)
        #### Setting menu actions ####
        self.connectButton.clicked.connect(self.connectCam)
        self.menuExit.triggered.connect(self.closeEvent)
        self.captureButton.clicked.connect(self.capture_image)
        self.recordButton.clicked.connect(self.record)
        self.liveplotButton.clicked.connect(self.liveplot)
        self.drawButton.clicked.connect(self.showShapes)
        self.changeExposure.valueChanged.connect(self.setExposure)
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
        #### Size and identity of camera frame ####
        self.window_width = self.cameraFrame.frameSize().width()
        self.window_height = self.cameraFrame.frameSize().height()
        self.cameraFrame = Camera(self.cameraFrame) 
        #### Create window for live data plotting ####
        self.plot1.plotItem.showGrid(True, True)
        self.plot1.plotItem.setContentsMargins(0,4,10,0)
        self.plot1.setLimits(xMin=0)
        self.plot1.setLabel('bottom', 'Time (s)')
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
        self.plotFFTblue.plotItem.setContentsMargins(0,4,16,0)
        self.plotFFTblue.setLabel('bottom', 'Frequency (Hz)')
        #### Drawing rectangles ####
        #### Set 1 second timer before connecting to camera ####
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(1)

    #### Start grabbing camera frames when Camera -> Connect is clicked ####
    def connectCam(self):
        global running
        running = True
        capture_thread.start()
        self.connectButton.setEnabled(False)
        self.connectButton.setText('Connecting...')
        self.statusbar.showMessage('Starting camera...')
        
    #### Change camera exposure ####
    def setExposure(self):
        global exposure
        exposure = self.changeExposure.value()
        
    #### Protocol for updating the video frames in the GUI ####
    def update_frame(self):
        global avg1, avg2, avg3, t0, t, p, x1, y1, x2, y2, a1, b1, a2, b2, c1, d1, c2, d2, samplenum, grower, sampletextset
        if not q.empty():
            self.connectButton.setText('Connected')
            frame = q.get()
            img = frame["img"]
            img_height, img_width, img_colors = img.shape
            #### Scaling the image from the camera ####
            scale_w = float(self.window_width) / float(img_width)
            scale_h = float(self.window_height) / float(img_height)
            scale = min([scale_w, scale_h])
            if scale == 0:
                scale = 1
            if scale != 1:
                img = cv2.resize(img, None, fx=scale, fy=scale, interpolation = cv2.INTER_CUBIC)
            #### Definng appearance of image ####
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            height, width, bpc = img.shape
            bpl = bpc * width
            image = QtGui.QImage(img.data, width, height, bpl, QtGui.QImage.Format_RGB888)
            print(type(image))
            #### Adding the camera to the screen ####
            self.cameraFrame.setImage(image)
            #### Updating live data ####
            if liveplotting:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                avg_1 = gray[y1:y2, x1:x2].mean()
                avg_1 = round(avg_1, 3)
                avg_2 = gray[b1:b2, a1:a2].mean()
                avg_2 = round(avg_2, 3)
                avg_3 = gray[d1:d2, c1:c2].mean()
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
        pixmap2 = QtGui.QPixmap(self.annotationCanvas.frameGeometry().width(), self.annotationCanvas.frameGeometry().height())
        pixmap2.fill(QtGui.QColor('black'))
        self.annotationCanvas.setPixmap(pixmap2)
        self.sampleLabel.setText('Current Sample: '+samplenum)
        self.growerLabel.setText('Current Grower: '+grower)
        self.annotateSampleName.setText('Sample: '+self.setSampleName.text())
        self.annotateOrientation.setText('Orientation: '+self.setOrientation.text())
        self.annotateLayer.setText('Growth layer: '+self.setGrowthLayer.text())
        self.annotateMisc.setText('Other notes: '+self.setMisc.text())
        if not sampletextset and samplenum != "None":
            self.setSampleName.setText(samplenum)
            sampletextset = True

    #### Saving a single image using the "Capture" button ####            
    def capture_image(self):
        global isfile, imnum, running, samplenum, path, filename
        if running:
            frame = q.get()
            img = frame["img"]
            #### Sequential file naming with timestamp ####
            imnum_str = str(imnum).zfill(2) # format image number as 01, 02, etc.
            timestamp = time.strftime("%b-%d-%Y %I.%M.%S %p") # formatting timestamp
            filename = samplenum+' '+imnum_str+' '+timestamp
            #### Save annotation ####
            a = self.annotationFrame.grab()
            a.save('annotation.jpg', 'jpg')
            #### Actually saving the file
            cv2.imwrite('picture.jpg', img)
            #### Splice images ####
            anno = Image.open('annotation.jpg')
            width1, height1 = anno.size
            pic = Image.open('picture.jpg')
            width2, height2 = pic.size
            w = width1
            h = height1 + height2
            image = Image.new('RGB', (w, h))
            image.paste(pic, (0,0))
            image.paste(anno, (0,height2))
            #### Save completed image ####
            image.save(path+filename+'.png')
            os.remove('annotation.jpg')
            os.remove('picture.jpg')
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
            timestamp = time.strftime("%b-%d-%Y %I.%M.%S %p") # formatting timestamp
            filename = samplenum+' '+vidnum_str+' '+timestamp            
            vidnum = int(vidnum) + 1
            out = cv2.VideoWriter(path+filename+'.avi', fourcc, 35.0, (640,480), True)
        if not recording and running:
            self.statusbar.showMessage('Video saved to '+path+' as '+filename+'.avi')
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
        global x1, y1, x2, y2, a1, b1, a2, b2, c1, d1, c2, d2, red, blue, yellow
        if self.drawCanvas.underMouse():
            if red:
                x1, y1 = event.pos().x()-10, event.pos().y()-70
            if green:
                a1, b1 = event.pos().x()-10, event.pos().y()-70
            if blue:
                c1, d1 = event.pos().x()-10, event.pos().y()-70
                
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
            peakfind1=str('Red peak at '+str(round(redpeak, 2))+' Hz or '+str(round(1/redpeak, 2))+' s')
            print(peakfind1)
            pen1 = pg.mkPen('r', width=1, style=QtCore.Qt.SolidLine)
            self.plotFFTred.plot(tf, np.abs(yf1[0:t_length//2]), pen=pen1, clear = True)
            #### Plot FFT of data from green rectangle ####
            green_no_dc = oldavg2 - np.mean(oldavg2)
            yf2 = rfft(green_no_dc)
            j = np.argmax(abs(yf2[0:t_length//2]))
            greenpeak = tf[j]
            peakfind2=str('Green peak at '+str(round(greenpeak, 2))+' Hz or '+str(round(1/greenpeak, 2))+' s')
            print(peakfind2)
            pen2 = pg.mkPen('g', width=1, style=QtCore.Qt.SolidLine)
            self.plotFFTgreen.plot(tf, np.abs(yf2[0:t_length//2]), pen=pen2, clear = True)
            #### Plot FFT of data from blue rectangle ####
            blue_no_dc = oldavg3 - np.mean(oldavg3)
            yf3 = rfft(blue_no_dc)
            k = np.argmax(abs(yf3[0:t_length//2]))
            bluepeak = tf[k]
            peakfind3=str('Blue peak at '+str(round(bluepeak, 2))+' Hz or '+str(round(1/bluepeak, 2))+' s')
            print(peakfind3)
            pen3 = pg.mkPen('b', width=1, style=QtCore.Qt.SolidLine)
            self.plotFFTblue.plot(tf, np.abs(yf3[0:t_length//2]), pen=pen3, clear = True) 

    #### Change sample ####
    def changeSample(self):
        global samplenum, grower, path, imnum, vidnum
        samplenum, ok = QtWidgets.QInputDialog.getText(w, 'Change sample name', 'Enter sample name: ')
        if ok:
            samplenum = samplenum
            imnum, vidnum = 1, 1
            self.sampleLabel.setText('Current Sample: '+samplenum)
            path = str('D:/ElliotYoung/Desktop/FRHEED/'+grower+'/'+samplenum+'/')
            #### Create folder to save images in if it doesn't already exist ####
            if not os.path.exists(path):
                os.makedirs(path)
    #### Change grower ####
    def changeGrower(self):
        global samplenum, grower, path, imnum, vidnum
        grower, ok = QtWidgets.QInputDialog.getText(w, 'Change grower', 'Who is growing? ')
        if ok:
            grower = grower
            imnum, vidnum = 1, 1
            self.growerLabel.setText('Current Grower: '+grower)
            path = str('C:/Users/ellio/Desktop/FRHEED/'+grower+'/'+samplenum+'/')
            #### Create folder to save images in if it doesn't already exist ####
            if not os.path.exists(path):
                os.makedirs(path)
    #### Saving notes ####
    def saveNotes(self):
        global path, filename
        timestamp = time.strftime("%b-%d-%Y %I.%M.%S %p") # formatting timestamp
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
    #### Close the program and terminate threads ####            
    def closeEvent(self, event):
        global running
        running = False
        print('Shutting down...')
        self.close()
        capture_thread.terminate()

#### Initialize threading with arguments for camera source, queue, frame dimensions and FPS ####
capture_thread = threading.Thread(target=grab, args = (0, q, 640, 480, 35))

#### Run the program, show the main window and name it 'FRHEED' ####
app = QtWidgets.QApplication(sys.argv)
w = FRHEED(None)
w.setWindowTitle('FRHEED')
w.show()
app.exec_()

#### Future additions/features:
####  - User-defined video file names

