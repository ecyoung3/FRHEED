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

import os
import sys
import ctypes
import time
import datetime
import traceback

from matplotlib import cm
import pyqtgraph as pg
from PyQt5 import uic, QtGui
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtCore import Qt, QObject
from PyQt5.QtCore import QRunnable, QThreadPool, pyqtSlot, pyqtSignal
import pyqt5ac
import pathvalidate

# Custom modules for running FRHEED
from modules import cameras, utils, build, guifuncs

# Find and load the resource file
pyqt5ac.main(config='resources/resources config.yml')

# Give Windows 10 information so it can set the taskbar icon correctly
app_id = 'FRHEED.FRHEED.FRHEED.FRHEED'
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)

# Load the UI file
form_class = uic.loadUiType('gui/FRHEED.ui')[0]

# Set default appearance of pyqtgraph plots
pg.setConfigOption('background', (25, 35, 45))
pg.setConfigOption('foreground', (255, 255, 255))

# Initialize the QApplication
app = QApplication(sys.argv)

class FRHEED(QMainWindow, form_class):
    def __init__(self, parent=None):
        QMainWindow.__init__(self, parent)
        
        # Construct the main window from the .ui file
        self.setupUi(self)
        self.setWindowTitle('FRHEED')
        self.show()
        self.app = app
        
        # Build components of UI that don't depend on camera selection
        build.core_ui(self)
        
        # Initialize configuration file
        self.configfile, self.config = utils.getConfig()
        
        # Set base location if it doesn't exist
        if not os.path.exists(self.config['Default']['path']):
            utils.setBasepath(self)
            
        # Check config options for base save location
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
        self.flir_connected, self.system, self.cam_list, self.flir_cam = items
        if self.flir_connected:
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
        self.threadpool.setMaxThreadCount(8)
        maxthreads = self.threadpool.maxThreadCount()
        print(f'Maximum number of threads: {maxthreads}')
              
        # Start displaying the camera feed
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
        worker.signals.finished.connect(self.finished_notice)
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
        if self.recording:
            rectime = (time.time() - self.recstart)
            disptime = str(datetime.timedelta(seconds=rectime))[:-5]
            self.mainstatus.setText(f'Current recording duration: {disptime}')
      
    def alarm_thread(self):
        if not self.beeping:
            self.beeping = True
            worker = Worker(utils.playAlarm, self)
            self.threadpool.start(worker)
        
    def resizeEvent(self, event):
        pass
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.leftpressed = True
        elif event.button() == Qt.RightButton:
            self.rightpressed = True
        elif event.button() == Qt.MidButton:
            self.midpressed = True
        
        # Drawing shapes
        if (event.button() == Qt.LeftButton and self.drawCanvas.underMouse()):
            self.beginpos = self.drawCanvas.mapFrom(self, event.pos())
            
            # Only draw shapes if they're toggled on
            if self.visibleshapes:
                
                # Begin drawing shapes
                self.drawCanvas.raise_()
                self.drawing = True
            
        # Resizing shapes
        if event.button() == Qt.RightButton and self.drawCanvas.underMouse():
            # Only resize if the cursor is near the shape when clicked
            if self.cursornearshape:
                self.resizing = True
                self.drawing = True
            
        # Change active shape
        if event.button() == Qt.MidButton and self.drawCanvas.underMouse():
            guifuncs.cycleColors(self)
            
    def mouseReleaseEvent(self, event):
        # Left button release
        if event.button() == Qt.LeftButton:
            self.leftpressed = False
            self.drawing = False
            
            # Normalize rectangle (prevent coordinates with negative values)
            rect = self.shapes[self.activecolor]['rect']
            if rect is not None:
                self.shapes[self.activecolor]['rect'] = rect.normalized()
            
        if event.button() == Qt.LeftButton and self.drawCanvas.underMouse():
            # Record the position where the mouse was released
            self.endpos = self.drawCanvas.mapFrom(self, event.pos())

            # Store the shape coordinates
            self.shapes[self.activecolor]['top left'] = self.beginpos
            self.shapes[self.activecolor]['bottom right'] = self.endpos
        
        # Right click to resize shapes
        if event.button() == Qt.RightButton:
            self.rightpressed = False
            self.drawing = False
            self.resizing = False
            self.movingside = None
            
            # Normalize rectangle
            rect = self.shapes[self.activecolor]['rect']
            if rect is not None:
                self.shapes[self.activecolor]['rect'] = rect.normalized()
            
        if event.button() == Qt.MidButton:
            self.midpressed = False
    
    def mouseMoveEvent(self, event):
        # Cursor position relative to the draw canvas
        draw_pos = self.drawCanvas.mapFrom(self, event.pos())
        
        # Use standard cursor when mouse isn't near the active shape
        if not self.cursornearshape:
            self.app.restoreOverrideCursor()
            
        # If the mouse is over the drawing canvas
        if self.drawCanvas.underMouse():
            # Detect cursor proximity to active shape to determine if
            # right clicking will begin resizing the shape
            if self.shapes[self.activecolor]['rect'] is not None:
                guifuncs.highlightSide(self, draw_pos)
                
            # Draw shapes
            if self.drawing:
                self.currpos = draw_pos
                guifuncs.drawShapes(self)
            
    def keyPressEvent(self, event: QtGui.QKeyEvent):
        # Placeholder for using control key as shortcut for common functions
        if event.key() == Qt.Key_Control:
            if self.drawCanvas.underMouse():
                pass
            
        # Clear active shape if the 'Delete' key is pressed while the
        # mouse is over the draw canvas while not live plotting
        if event.key() == Qt.Key_Delete and self.drawCanvas.underMouse():
            if not self.plotting:
                ac = self.activecolor
                self.shapes[ac]['top left'] = None
                self.shapes[ac]['bottom right'] = None
                self.shapes[ac]['rect']= None
                guifuncs.drawShapes(self, deleteshape = True)
                self.cursornearshape = False
                
                # Disable the live plot button if no shapes are drawn
                numshapes = sum(1 for col in self.shapes if 
                                self.shapes[col]['top left'])
                if numshapes == 0:
                    self.liveplotButton.setEnabled(False)

    def closeEvent(self, event, **kwargs):
        # Stop any alarms
        self.beeping = False
        
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
        
        # Clear the threadpool so code doesn't execute after exiting
        self.threadpool.clear()
        
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
'''
FEATURES TO ADD:
    - controls for additional plot options (filtering, scrolling)
    - hover color for right click menus
    - allow user to change live plot viewbox during plotting
    - add laps to stopwatch
    - renaming plot tabs for stored data
    - shape translational motion
    - shortcuts for common buttons
    - cycle backwards through colors
    - selectively show/hide lines on plotted data
    - get Vimba/Firewire cameras working
    - adding video playback/analysis
    - shape translational motion
    - add 1D line plot for strain analysis
    - 3D plotting
    - arbitrary image masks
    - update method of inputting timer amount
'''
'''
THINGS TO FIX:
    - drawn shapes and intensity regions should resize with frame
    - bugs with changing user/sample and inputting invalid characters
    - study video recording stability
        - snip camera frame instead of using raw camera inupt 
            for more stable performance?
    - the goddamn zooming/crashing bug apparently isn't fixed...
        - signal proxy to limit signal rate?
        - change zooming mode to have user drag-select an area instead
            of having a scroll bar?
    - figure out why FLIR camera becomes incredibly laggy after long
         time idling in Spyder (i.e. overnight)
    - tooltips
    - line overlap with y-axis in data plots
    
'''