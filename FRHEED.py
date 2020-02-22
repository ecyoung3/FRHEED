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

import os  # for checking/creating computer directories
import sys  # for system-specific parameters
import ctypes # for setting the taskbar icon in Windows 10
import configparser  # for reading a configuration file
import cv2  # for image processing
import numpy as np  # for math and array processing
import queue  # for handling threads
import threading  # for threading
import multiprocessing as mupro
import concurrent.futures
import time  # for keeping track of time
import datetime
import atexit # exit event handling
import traceback

from colormap import Colormap  # for creating custom colormaps
from matplotlib import cm  # for using colormaps
import matplotlib.figure as mpl_fig
import matplotlib.animation as anim
from matplotlib.backends.backend_qt5agg import FigureCanvas
from PIL import Image, ImageQt  # for image processing
from PyQt5 import uic, QtWidgets, QtGui  # for the GUI
from PyQt5.QtWidgets import QApplication, qApp, QMainWindow, QVBoxLayout # stuff for main GUI window
from PyQt5.QtWidgets import QDialog, QMessageBox, QInputDialog # popup windows
from PyQt5.QtWidgets import QPushButton, QLabel, QSizePolicy # GUI elements
from PyQt5.QtGui import QIcon, QImage, QMouseEvent, QCursor, QPixmap, QColor, QPen, QPainter # for the GUI
from PyQt5.QtCore import QSize, Qt, QTimer, QRunnable, QThreadPool, pyqtSlot, pyqtSignal, QObject # for the GUI
import qimage2ndarray
import pyqtgraph as pg  # for plotting
from scipy.fftpack import rfft  # for performing real FFT on data
import PySpin # for connecting to and controlling the FLIR camera
import pyqt5ac # for importing .qrc resource file for the UI
import pathvalidate

# Custom modules for running FRHEED
from modules import cameras, utils, build, guifuncs

try:
    from pymba import Vimba, Frame # for connecting to Allied Vision Stingray firewire cameras
    pymba_imported = True
except Exception as ex:
    pymba_imported = False
    print('ERROR: {}'.format(ex))

# Find and load the resource file
pyqt5ac.main(config='resources/resources config.yml')

# Give Windows 10 the app information so it can set the taskbar icon correctly
app_id = 'FRHEED.FRHEED.FRHEED.FRHEED'
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)

# Load the UI file, which should be located in the same folder as FRHEED.py
form_class = uic.loadUiType('gui/FRHEED.ui')[0]

# Set default appearance of plots. Not needed if using a comprehensive stylesheet/palette
pg.setConfigOption('background', (25, 35, 45)) # background color
pg.setConfigOption('foreground', (255, 255, 255))  # white axes lines and labels

# Initialize the QApplication so PyQt widgets can be displayed/executed
app = QApplication(sys.argv)  # run the app with the command line arguments (sys.argv) passed to it

class FRHEED(QMainWindow, form_class):
    def __init__(self, parent=None):
        # Set up the main UI. Do this so parent classes can inherit the appearance/properties.
        QMainWindow.__init__(self, parent) # initialize the main window
        self.buttons = qApp.mouseButtons() # shortcut to checking which mouse buttons are pressed
        self.setupUi(self) # this is where the UI is actually constructed from the FRHEED.ui file
        self.setWindowTitle('FRHEED')
        self.show() # show the window and all children windows (e.g. dialogs)
        self.app = app
        # Build components of UI that don't depend on camera selection
        build.core_ui(self)
        
        # Load sample image for RHEED simulation
        self.rheed_sample_img = np.array(Image.open('rheed_spots.png'))
        self.frameindex = 0
        
        # Initialize configuration file
        self.configfile, self.config = utils.getConfig()
        
        # Set base location if it doesn't exist
        if not os.path.exists(self.config['Default']['path']):
            utils.setBasepath(self)
            
        # Load config options
        self.basepath = self.config['Default']['path']
        
        # Check to make sure the basepath is valid
        test = os.path.join(self.basepath, '')
        if not pathvalidate.is_valid_filepath(test,
                                              platform = 'Windows'):
            utils.setBasepath(self)
            
        # Check to make sure the user directory is valid and exists
        self.user = self.user = self.config['Default']['user']
        test = os.path.join(self.basepath, self.user, '')
        if not pathvalidate.is_valid_filepath(test,
                                              platform = 'Windows'):
            utils.setUser(self, changesample = False)
        elif not os.path.exists(test):
            os.path.makesdirs(test)
            
        # Check to make sure the sample directory is valid and exists
        self.sample = self.config['Default']['sample']
        test = os.path.join(self.basepath, self.user, self.sample, '')
        if not pathvalidate.is_valid_filepath(test,
                                              platform = 'Windows'):
            utils.setSample(self)
        elif not os.path.exists(test):
            os.makedirs(test)
        
        # Set the path that collected data will be saved into
        self.activepath = os.path.join(self.basepath, self.user, 
                                       self.sample, '')
        
        # Update user and sample text
        self.sampleLabel.setText(self.sample)
        self.userLabel.setText(self.user)
        
        # Set up the default colormap
        try:
            self.cmap = cm.get_cmap(self.config['Default']['colormap'])
        except:
            self.cmap = cm.get_cmap('gist_gray')
        
        # No camera selected by default
        self.camtype = None
        
        # Detect cameras and choose one to connect to
        *items, = cameras.FLIR().connectCam()
        self.flir_result, self.system, self.cam_list, self.flir_cam = items
        if self.flir_result:
            self.serial_number = self.flir_cam.GetUniqueID()
        self.usb_cam = cameras.USB().connectCam()
        cameras.selectionDialog(self).chooseCamera(self.system, quitting=True)
        
        if self.camtype == 'FLIR':
            self.cam = self.flir_cam
        elif self.camtype == 'USB':
            self.cam = self.usb_cam
            self.system = self.cam_list = self.flir_cam = None
        
        # Build camera-related components of the UI
        build.camera_ui(self)
        
        # Build the main menu
        build.mainmenu(self, self.system)
        
        # Create threadpool
        self.threadpool = QThreadPool()
        # self.threadpool.setMaxThreadCount(6)
        maxthreads = self.threadpool.maxThreadCount()
        print(f'Maximum number of threads: {maxthreads}')
              
        # Start updating the GUI
        self.frame_thread()
        
    def frame_thread(self):
        self.running = True
        worker = Worker(guifuncs.liveStream, self)
        worker.signals.ready.connect(self.update_pixmap)
        worker.signals.recframe.connect(self.save_video)
        worker.signals.plotframe.connect(self.calc_thread)
        self.threadpool.start(worker)
        
    def update_pixmap(self):
        self.cameraCanvas.setPixmap(self.pim)
        
    def finished_notice(self, **kwargs):
        return
        
    def calc_thread(self, frame):
        worker = Worker(guifuncs.calculateIntensities, self, frame)
        self.threadpool.start(worker)
        
    def plot_thread(self, **kwargs):
        worker = Worker(guifuncs.updatePlots, self)
        worker.signals.finished.connect(self.finished_notice)
        self.threadpool.start(worker)
          
    def grab_frame(self):
        worker = Worker(guifuncs.captureImage, self)
        self.threadpool.start(worker)
        
    def save_video(self, frame):
        # Write the frame to file
        try:
            self.writer.write(frame)
        except:
            return
        
        # Show the recording time in the statusbar
        rectime = (time.time() - self.recstart)
        disptime = str(datetime.timedelta(seconds=rectime))[:-5]
        self.mainstatus.setText(f'Current recording duration: {disptime}')
        
    def resizeEvent(self, event):
        pass
    
    def mousePressEvent(self, event):
        # Left button click
        if event.button() == Qt.LeftButton and self.drawCanvas.underMouse():
            self.beginpos = self.drawCanvas.mapFrom(self, event.pos())
            
            # Only draw shapes if they're toggled on
            if self.visibleshapes:
                
                # Begin drawing
                self.drawCanvas.raise_()
                self.drawing = True
            
        # Scroll wheel click
        if event.button() == Qt.MidButton and self.drawCanvas.underMouse():
            guifuncs.cycleColors(self)
            
    def mouseReleaseEvent(self, event):
        # Left button release
        if event.button() == Qt.LeftButton and self.drawCanvas.underMouse():
            # Record the position where the mouse was released
            self.endpos = self.drawCanvas.mapFrom(self, event.pos())

            # Stop drawing
            self.drawing = False
            
            # Store the shape coordinates
            self.shapes[self.activecolor]['start'] = self.beginpos
            self.shapes[self.activecolor]['end'] = self.endpos
    
    def mouseMoveEvent(self, event):
        if self.drawCanvas.underMouse() and self.drawing:
            self.currpos = self.drawCanvas.mapFrom(self, event.pos())
            guifuncs.drawShapes(self)
            
    def keyPressEvent(self, event: QtGui.QKeyEvent):
        if event.key() == Qt.Key_Control:
            if self.drawCanvas.underMouse():
                pass
            # eventually make it so ctrl + scroll zooms the image
        if event.key() == Qt.Key_Delete and self.drawCanvas.underMouse():
            if not self.plotting:
                ac = self.activecolor
                self.shapes[ac]['start'] = None
                self.shapes[ac]['end'] = None
                guifuncs.drawShapes(self, deleteshape = True)

    def closeEvent(self, event, **kwargs):
        # Stop plotting
        self.plotting = False
        
        # Stop video recording if it's running
        if self.recording:
            guifuncs.recordVideo(self)
        
        # Stop streaming
        self.running = False
        
        # Disconnect cameras
        try:
            cameras.FLIR().disconnect(self.system)
            cameras.USB().disconnect()
        except:
            pass
        
        # Close the main window
        self.close()
        
        # Quit the application
        print('Exiting...')
        app.quit()
        
class WorkerSignals(QObject):
    ready = pyqtSignal()
    plotready = pyqtSignal()
    recframe = pyqtSignal(object)
    plotframe = pyqtSignal(object)
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)
  
class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        
        self.kwargs['ready'] = self.signals.ready
        self.kwargs['recframe'] = self.signals.recframe
        self.kwargs['plotframe'] = self.signals.plotframe
        self.kwargs['finished'] = self.signals.finished
        self.kwargs['error'] = self.signals.error
        self.kwargs['plotready'] = self.signals.plotready
        
    @pyqtSlot()
    def run(self):
        try:
            self.running = True
            result = self.fn(*self.args, **self.kwargs)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()
        

# The __name__ == '__main__' condition is True if the script is run
# directly as opposed to being called by another file (i.e. imported)
if __name__ == '__main__':
    w = FRHEED(None)
    app.exec_()

# TODO LIST
"""
- figure out why FLIR camera becomes incredibly laggy after long time
    idling in Spyder (i.e. overnight)
- get Vimba/Firewire cameras working
- adding video playback/analysis
- fix tooltips
- ability to popout camera
- shape translational motion
- add 1D line plot for strain analysis
- 3D plotting
- arbitrary masks
- update method of inputting timer amount
"""
'''
BUGS:
    - Zooming the image too quickly (i.e. via scroll wheel) will crash
        the program
    
    
'''