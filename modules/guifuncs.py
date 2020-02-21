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

import sys
import os
import configparser
import numpy as np
import queue
import time
import datetime
import cv2
import qimage2ndarray
from matplotlib import cm
from PIL import Image, ImageQt
from PyQt5 import uic, QtWidgets, QtGui  # for the GUI
from PyQt5.QtWidgets import QApplication, qApp, QMainWindow, QVBoxLayout
from PyQt5.QtWidgets import QDialog, QMessageBox, QInputDialog
from PyQt5.QtWidgets import QPushButton, QLabel, QSizePolicy
from PyQt5.QtGui import QIcon, QImage, QPixmap, QColor, QPen, QPainter
from PyQt5.QtGui import QMouseEvent, QCursor
from PyQt5.QtCore import QSize, Qt, QTimer, QRect, pyqtSlot
import pyqtgraph as pg

from . import cameras, utils

# =============================================================================
# THREADED FUNCTIONS
# =============================================================================

def liveStream(self, ready, recframe, plotframe, **kwargs):
    while self.running:
        # Grab the camera frame
        img = cameras.grabImage(self)
        
        # Go back to the start of the while loop (skip subsequent code) if img is None
        if img is None:
            continue
        
        # Store the image if it is not None
        if img is not None:
            self.img = img.copy()
           
        # Display the total number of dropped frames in the statusbar
        self.droppedframestatus.setText(f'Total dropped frames: {self.droppedframes} ')
            
        # First frame in the real FPS calculation
        if self.framecount == 0:
            self.firstframe = time.time()
            
        # Image inversion
        if self.inverted:
            self.img = np.invert(self.img)
            
        # Background subtraction
        if self.background is not None and self.backgroundset:
            self.img = cv2.subtract(self.img, self.background)
            
        # Get the height and width of the image
        self.img_height, self.img_width = self.img.shape
        
        # Set the minimum zoom level
        self.zoomSlider.setMinimum(int(np.min([320/self.img_width, 240/self.img_height])*100))
        
        # Zoomable image
        if not self.autoscaleCheckbox.isChecked():
            if not self.zoomSlider.isEnabled():
                self.zoomSlider.setEnabled(True)
            self.scaled_w = int(self.zoom * self.img_width)
            self.scaled_h = int(self.zoom * self.img_height)
          
        # Autoscaling image
        else:
            if self.zoomSlider.isEnabled():
                self.zoomSlider.setEnabled(False)
            self.scale_w = float(self.parentScrollArea.width()-4) / float(self.img_width)
            self.scale_h = float(self.parentScrollArea.height()-4) / float(self.img_height)
            self.scale = min([self.scale_w, self.scale_h])
            self.scaled_w = int(self.scale * self.img_width)
            self.scaled_h = int(self.scale * self.img_height)
            
            # Resize camera canvas (displays camera feed) and draw canvas (displays shapes) to proper size
            if (self.scaled_w < 320 or self.scaled_h < 240):
                self.scaled_w, self.scaled_h = 320, 240
                
        # Resize the necessary objects
        self.cameraCanvas.resize(self.scaled_w, self.scaled_h)
        self.drawCanvas.resize(self.scaled_w, self.scaled_h)
        self.parentFrame.resize(self.scaled_w, self.scaled_h)
        self.annotationFrame.setFixedSize(self.scaled_w, self.anno_height)
        
        # Linear interpolation (INTER_LINEAR) would be slightly faster but produce a lower quality image.
        self.scaled_img = cv2.resize(self.img, dsize=(self.scaled_w, self.scaled_h), interpolation=cv2.INTER_CUBIC)
        
        
        if self.plotting and self.liveplotButton.isChecked():
            plotframe.emit(self.scaled_img)
        
        # Convert image and apply colormap if the width is below 1280 pixels
        if self.scaled_w < 1280:
            # Remove the alpha channel since it's always 255 anyway
            self.cimg = self.cmap(self.scaled_img, bytes=True)[:,:,:-1]
            
            # Keep the array uint8 data type; not sure why this is necessary
            # but QImage conversion fails otherwise
            self.cimg = np.require(self.cimg, 'uint8', 'C').copy()
            
            # Convert to a QImage
            self.qim = QImage(self.cimg, self.scaled_w, self.scaled_h, 3*self.scaled_w, QImage.Format_RGB888)
        
        elif self.scaled_w >= 1280 or self.cmap.name == 'gist_gray':
            # Convert 8-bit grayscale numpy array to QImage
            self.qim = qimage2ndarray.gray2qimage(self.scaled_img)
        
        # Creating QPixmap from QImage
        self.pim = QPixmap.fromImage(self.qim)
        
        # Video recording
        if self.recording:
            # Make sure the output is a fixed size
            vidframe = cv2.resize(self.img, dsize=self.recsize, interpolation=cv2.INTER_CUBIC)
            
            # Apply colormap as above
            cim = self.cmap(vidframe, bytes=True)[:,:,:-1]
            cim = np.require(cim, 'uint8', 'C').copy()
            
            # Convert numpy array from RGB -> BGR
            bgr = cim[...,::-1]
            
            # The video writer suffers from a similar problem to the QLabel update and 
            # will crash if it tries to write empty frames. Therefore it is critical 
            # that we use the emit method again to make sure the writer is actually 
            # receiving complete frames.
            recframe.emit(bgr.copy())     
        
        # Calculate and display the real FPS every 30 frames
        self.framecount += 1
        if self.framecount == 30:
            self.realfps = 30/(time.time()-self.firstframe)
            self.fpsstatus.setText('FPS: {:.2f}'.format(self.realfps))
            self.framecount = 0
        
        # THIS IS CRUCIAL. Emit a signal to trigger the camera frame to actually update.
        # If you try to set the camera frame in this function, the program will crash
        # if the image is zoomed too quickly or scrolled while zoomed in.
        ready.emit()

# =============================================================================
# FUNCTIONS FOR IMAGE PROCESSING AND CAMERA SETTINGS
# =============================================================================
            
def changeColormap(self, cmap):
    sending_button = self.sender()
    self.cmap = cm.get_cmap(name=cmap)
    self.colormapstatus.setText('Current colormap: {}'.format(sending_button.text()))
    return self.cmap
    
def setBackground(self):
    if self.img is not None and not self.backgroundset:
        self.backgroundset = True
        self.background = self.img
        self.clearbgButton.setEnabled(True)
        self.clearbgButton.setText('Clear Background')
        self.backgroundButton.setEnabled(False)
        self.backgroundButton.setText('Background Set')
        
def clearBackground(self):
    self.background = None
    self.backgroundset = False
    self.clearbgButton.setEnabled(False)
    self.clearbgButton.setText('No Background Set')
    self.backgroundButton.setEnabled(True)
    self.backgroundButton.setText('Set Background')

def invertImage(self):
    self.inverted = not self.inverted
    if self.inverted:
        self.invertButton.setText('Un-Invert Image')
    else:
        self.invertButton.setText('Invert Image')
    
def zoomImage(self):
    if not self.autoscaleCheckbox.isChecked():
        self.zoom = self.zoomSlider.value()/100.
        self.zoomvalueLabel.setText('{}%'.format(int(100*self.zoom)))

def setExposure(self):
    if self.camtype == 'FLIR':
        expotime = self.changeExposure.value()
        exposure = float(expotime * 1000)
        try:
            self.cam.ExposureTime.SetValue(exposure)
        except:
            pass
    elif self.camtype == 'USB':
        expo = self.changeExposure.value()
        self.cam.set(cv2.CAP_PROP_EXPOSURE, expo)

def setGamma(self):
    if self.camtype == 'FLIR':
        gamma_val = self.gammaSlider.value() 
        self.scaled_gamma = round((1/100)*gamma_val, 2)
        self.gammaValue_Label.setText("{:.2f}".format(self.scaled_gamma))
        self.cam.Gamma.SetValue(self.scaled_gamma)
        
def setBlackLevel(self):
    if self.camtype == 'FLIR':
        blacklevel_val = self.blacklevelSlider.value()
        self.scaled_blacklevel = round((1/100)*blacklevel_val, 2)
        self.blacklevelValue_Label.setText("{:.2f}".format(self.scaled_blacklevel))
        self.cam.BlackLevel.SetValue(self.scaled_blacklevel)

def setGain(self):
    if self.camtype == 'FLIR':
        gain_val = self.gainSlider.value()
        self.scaled_gain = round((1/100)*gain_val, 2)
        self.gainValue_Label.setText("{:.2f}".format(self.scaled_gain))
        self.cam.Gain.SetValue(self.scaled_gain)

def setDefaultConditions(self):
    if self.camtype == 'FLIR':
        self.config['Default']['flir_gamma'] = str(self.scaled_gamma)
        self.config['Default']['flir_blacklevel'] = str(self.scaled_blacklevel)
        self.config['Default']['flir_gain'] = str(self.scaled_gain)
        expotime = self.changeExposure.value()
        self.config['Default']['flir_exposure'] = str(int(expotime*1000))
    if self.camtype == 'USB':
        self.config['Default']['usb_exposure'] = str(self.changeExposure.value())
    
    # Save config changes
    with open('config.ini', 'w') as cfg:
        self.config.write(cfg)
        
    print('Default camera settings updated.')

def setImageProfile(self):
    # Get the button which triggered this function
    sending_button = self.sender()
    b = sending_button.objectName()
    
    # Get the profile number (1, 2, or 3) and action ('save' or 'load')
    num = b[-1]
    profile = f'Profile {num}'
    action = b[:4]
    
    # Get the stored profile names
    name1 = self.config['Profile 1']['profile_name']
    name2 = self.config['Profile 2']['profile_name']
    name3 = self.config['Profile 3']['profile_name']
    
    # Saving profiles
    if action == 'save':
        # I could probably write a function to handle this but didn't bother
        if profile == 'Profile 1':
            if self.editProfile1Name.text() == '':
                QMessageBox.warning(self, 
                    'Warning', 
                    'Please enter a profile name before saving.')
            elif self.editProfile1Name.text() in (name2, name3):
                QMessageBox.warning(self, 
                    'Warning', 
                    'A profile with that name already exists.\n' + 
                    'Please choose a unique name.')
                self.editProfile1Name.setText(name1)
                return
            else:
                self.config[profile]['profile_name'] = self.editProfile1Name.text()
        if profile == 'Profile 2':
            if self.editProfile1Name.text() == '':
                QMessageBox.warning(self, 
                    'Warning', 
                    'Please enter a profile name before saving.')
            elif self.editProfile2Name.text() in (name1, name3):
                QMessageBox.warning(self, 
                    'Warning', 
                    'A profile with that name already exists.\n' + 
                    'Please choose a unique name.')
                self.editProfile2Name.setText(name2)
                return
            else:
                self.config[profile]['profile_name'] = self.editProfile2Name.text()
        if profile == 'Profile 3':
            if self.editProfile1Name.text() == '':
                QMessageBox.warning(self, 
                    'Warning', 
                    'Please enter a profile name before saving.')
            elif self.editProfile3Name.text() in (name1, name2):
                QMessageBox.warning(self, 
                    'Warning', 
                    'A profile with that name already exists.\n' + 
                    'Please choose a unique name.')
                self.editProfile3Name.setText(name3)
                return
            else:
                self.config[profile]['profile_name'] = self.editProfile3Name.text()
                
        # Caution the user to make sure they want to overwrite a saved profile
        reply = QMessageBox.question(self, 
                     'Caution', 
                     'Are you sure you wish to overwrite the current profile?',
                     QMessageBox.Yes, QMessageBox.No)
        
        # Exit if the user doesn't want to override an existing profile
        if reply == QMessageBox.No:
            return
        
        # Store camera settings to profile in config file
        if self.inverted:
            self.config[profile]['inverted'] = 'True'
        if not self.inverted:
            self.config[profile]['inverted'] = 'False'  
        if self.camtype == 'FLIR':
            self.config[profile]['flir_exposure'] = str(1000*int(self.changeExposure.value()))
            self.config[profile]['flir_gamma'] = str(self.scaled_gamma)
            self.config[profile]['flir_blacklevel'] = str(self.scaled_blacklevel)
            self.config[profile]['flir_gain'] = str(self.scaled_gain)
        if self.camtype == 'USB':
            self.config[profile]['usb_exposure'] = str(int(self.changeExposure.value()))
        self.config[profile]['colormap'] = self.cmap.name
        
        # Update the high exposure default in the config file
        with open('config.ini', 'w') as cfg:
            self.config.write(cfg)
       
    # Loading profiles
    if action == 'load':
        # Update line edit text with loaded profile name
        if profile == 'Profile 1':
            self.editProfile1Name.setText(name1)
        if profile == 'Profile 2':
            self.editProfile2Name.setText(name2)
        if profile == 'Profile 3':
            self.editProfile3Name.setText(name3)
            
        # Apply loaded profile camera settings
        if self.config[profile]['inverted'] == 'True':
            self.inverted = True
            self.invertButton.setText('Un-Invert Image')
        if self.config[profile]['inverted'] == 'False':
            self.inverted = False
            self.invertButton.setText('Invert Image')
        if self.camtype == 'FLIR':
            exposure = int(self.config[profile]['flir_exposure'])
            self.changeExposure.setValue(exposure/1000)
            self.cam.ExposureTime.SetValue(exposure)
            scaled_gamma = float(self.config[profile]['flir_gamma'])
            self.gammaSlider.setValue(scaled_gamma*100)
            self.cam.Gamma.SetValue(scaled_gamma)
            scaled_blacklevel = float(self.config[profile]['flir_blacklevel'])
            self.blacklevelSlider.setValue(scaled_blacklevel*100)
            self.cam.BlackLevel.SetValue(scaled_blacklevel)
            scaled_gain = float(self.config[profile]['flir_gain'])
            self.gainSlider.setValue(scaled_gain*100)
            self.cam.Gain.SetValue(scaled_gain)
        if self.camtype == 'USB':
            exposure = int(self.config[profile]['usb_exposure'])
            self.cam.set(cv2.CAP_PROP_EXPOSURE, exposure)
            self.changeExposure.setValue(exposure)
            
        # matplotlib is dumb and doesn't remember custom colormap names
        colormap = self.config[profile]['colormap']
        if colormap != 'my_color_map':
            self.cmap = cm.get_cmap(colormap)
        else:
            self.cmap = cm.get_cmap('frheed_green')

# =============================================================================
# FUNCTIONS FOR CAPTURING IMAGES AND VIDEO & CHANGING ANNOTATION
# =============================================================================
 
def captureImage(self, **kwargs):
    if self.running and self.cimg is not None:
        # Generate filename for image to be saved as
        num = str(self.img_number).zfill(2) # format 0 as 00
        timestamp = time.strftime("%Y-%m-%d %I_%M_%S %p")
        filename = f'{self.sample} {num} {timestamp}.png'
        
        # Set save path
        filepath = os.path.join(self.activepath, filename)
        
        # Grab the annotation frame as a QPixmap
        a = self.annotationFrame.grab()
        ah = a.height()
        
        # Get the camera image and convert it to a PIL image
        i = self.cimg
        im = Image.fromarray(self.cimg)
        
        # Get dimensions for stitched image
        w = i.shape[1]
        h = i.shape[0] + ah
        
        # Convert QPixmap to PIL image by saving and reopening with PIL
        a.save('a.png', 'png')
        a = Image.open('a.png')
        
        # Create image template to paste the camera image and annotation into
        ima = Image.new('RGB', (w, h))
        
        # Stitch the image together
        ima.paste(im, (0, 0))
        ima.paste(a, (0, i.shape[0]))
        
        # Save the image
        ima.save(filepath)
        
        # Remove the temporary annotation image
        a.close()
        os.remove('a.png')
        
        # Increment the image number
        self.img_number += 1
        
        # Set statusbar text to show that an image was captured
        self.mainstatus.setText(f'Image saved as {filename}')
        
def recordVideo(self):
    # Prevent the recorder from being started and stopped too quickly
    try:
        rectime = time.time() - self.recstart
        if rectime < 0.5:
            return
    except:
        pass
    
    self.recording = not self.recording
    if self.recording and self.running and self.cimg is not None:
        
        self.recstart = time.time()
        num = str(self.vid_number).zfill(2) # format 0 as 00
        timestamp = time.strftime("%Y-%m-%d %I_%M_%S %p")
        self.vidname = f'{self.sample} {num} {timestamp}.mp4'
        filepath = os.path.join(self.activepath, self.vidname)
        
        # Make sure the frame size stays constant throughout recording
        # Making the recording larger would require a dedicated thread
        self.recsize = (800, 600)
        
        # Video writer format
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        
        # Create video writer object that will save the frames to an .mp4
        fps = int(self.realfps) if self.realfps is not None else 20
        self.writer = cv2.VideoWriter(filename = filepath, 
                                      fourcc = fourcc, 
                                      fps = fps, 
                                      frameSize = self.recsize, 
                                      isColor = True
                                      )

    if not self.recording:
        self.mainstatus.setText(f'Video saved as {self.vidname}')
        try:
            if self.writer.isOpened():
                self.writer.release()
                print('Released video writer...')
        except:
            pass
        finally:
            pass

def annotationSampleText(self):
    txt = f'Sample:  {self.setSampleName.text()}'
    self.annotateSampleName.setText(txt)

def annotationOrientationText(self):
    txt = f'Orientation:  {self.setOrientation.text()}'
    self.annotateOrientation.setText(txt)

def annotationLayerText(self):
    txt = f'Growth Layer:  {self.setGrowthLayer.text()}'
    self.annotateLayer.setText(txt)

def annotationMiscText(self):
    txt = f'Notes:  {self.setMisc.text()}'
    self.annotateMisc.setText(txt)

def annotationColor(self):
    sending_button = self.sender()
    button_name = sending_button.objectName()
    if button_name == 'annobgcolorButton':
        c = QtWidgets.QColorDialog()
        if c.exec_() == QtWidgets.QDialog.Accepted:
            self.bgc = c.currentColor().name()
            self.annotationFrame.setStyleSheet('background-color: {}'.format(self.bgc))
    if button_name == 'annotextcolorButton':
        c = QtWidgets.QColorDialog()
        if c.exec_() == QtWidgets.QDialog.Accepted:
            self.txtc = c.currentColor().name()
            self.annotationFrame.setStyleSheet('color: {}'.format(self.txtc))

# =============================================================================
# FUNCTIONS FOR PLOTTING          
# =============================================================================

def togglePlot(self):
    self.plotting = not self.plotting
    if self.plotting:
        self.plotstart = time.time()
        self.plot_thread()
    else:
        storeData(self, self.shapes)
        plotStoredData(self)
        for col in self.shapes.keys():
            self.shapes[col]['data'] = []
            self.shapes[col]['time'] = []
            self.shapes[col]['plot'].clear()

def calculateIntensities(self, frame, finished, **kwargs):
    if not self.plotting or not self.liveplotButton.isChecked():
        return
    plotnum = 0
    for col in self.shapes.keys():
        start = self.shapes[col]['start']
        end = self.shapes[col]['end']
        if start is not None and end is not None:
            data = self.shapes[col]['data']
            
            # Get the min/max coordinates for the mask shape
            xmin, xmax = tuple(sorted([start.x(), end.x()]))
            ymin, ymax = tuple(sorted([start.y(), end.y()]))
            
            # Cut the frame data for extracting intensity
            cut = frame[ymin:ymax, xmin:xmax]
            
            # Sum the intensities
            cts = np.sum(cut)

            # Scale the intensity counts (divide by number of pixels in mask)
            rel_cts = cts/cut.size
            
            # Append the data point
            data.append(rel_cts)
            
            # Shift the plot to try to avoid overlapping with other plots
            data = data*(1+plotnum)
            
            # Store the time data
            t = time.time() - self.plotstart
            self.shapes[col]['time'].append(t)
            
            # Increment plot number for vertical shifting
            plotnum += 1
            
    # Emit the finished signal (probably not essential)
    finished.emit()

def updatePlots(self, finished, timespan: float = 5.0, **kwargs):
    while self.plotting:
        # Count the number of active plots
        numplots = sum(1 for col in self.shapes if self.shapes[col]['data'])
        for col in self.shapes.keys():
            t = self.shapes[col]['time']
            data = self.shapes[col]['data']
            pos = 0
            if t:
                if max(t)-min(t) > timespan:
                    pos = list(map(lambda s: s > t[-1]-timespan, t)).index(True)
                    self.livePlotAxes.setXRange(t[pos], t[-1], padding=0)
                elif numplots <= 1:
                    bot = np.amin([t[-1]-timespan, 0])
                    self.livePlotAxes.setXRange(bot, t[-1], padding=0)
            self.shapes[col]['plot'].setData(
                t[pos:], 
                data[pos:]
                )
        time.sleep(0.03) # give time for the GUI to update
        finished.emit() # emit signal because otherwise the thread crashes

def storeData(self, shapes: dict):
    num_stored_datasets = len([x for x in self.stored_data.keys()])
    new_entry = str(num_stored_datasets+1)
    self.stored_data[new_entry] = {}
    for color in shapes.keys():
        self.stored_data[new_entry][color] = {}
        t = shapes[color]['time']
        data = shapes[color]['data']
        self.stored_data[new_entry][color]['time'] = t
        self.stored_data[new_entry][color]['data'] = data

def plotStoredData(self):
    dataset_list = [x for x in self.stored_data.keys()]
    num_stored_datasets = len(dataset_list)
    if num_stored_datasets == 0:
        return
    axes = utils.addPlotTab(self.oldDataTabs)
    utils.formatPlots(axes)
    newest_dataset = dataset_list[-1]
    plots = utils.addPlots(axes)
    for color in self.stored_data[newest_dataset]:
        t = self.stored_data[newest_dataset][color]['time']
        data = self.stored_data[newest_dataset][color]['data']
        if t and data:
            plots[color].setData(t, data)
        
def plotFFT(self):
    pass

# =============================================================================
# FUNCTIONS FOR MODIFYING SHAPE OVERLAYS AND IMAGE SELECTION AREA
# =============================================================================

def cycleColors(self):
    # There are only 5 colors in the list so the index needs to be <= 4
    if self.colorindex < 4:
        self.colorindex += 1
    else:
        self.colorindex = 0
        
    # Cycle to the next color (red -> green -> blue -> orange -> purple -> red)
    self.activecolor = list(self.shapes.keys())[self.colorindex]
    
    # Update the button
    self.rectButton.setStyleSheet(
        f'qproperty-icon: url(:/icons/icons/{self.activecolor} rect.png)')

def showShapes(self):
    self.visibleshapes = not self.visibleshapes
    if not self.visibleshapes:
        self.drawCanvas.hide()
    else:
        self.drawCanvas.show()
    
def drawShapes(self, deleteshape: bool = False):
    if not (self.drawing and self.visibleshapes and self.drawCanvas.underMouse()
        or deleteshape):
        return
    
    # Load the current color
    color = self.shapes[self.activecolor]['color']
    
    # Create the pixmap that shapes will be drawn on
    pmap = QPixmap(self.drawCanvas.size())
    pmap.fill(QColor('transparent'))
    
    # Create the QPainter object
    qp = QPainter(pmap)
    
    # Set the brush color
    pen = QtGui.QPen(QColor(*color))
    qp.setPen(pen)
    if not deleteshape:
        qp.drawRect(QRect(self.beginpos, self.currpos))

    # x, y = self.beginpos.x(), self.beginpos.y()
    # w, h = self.currpos.x() - x, self.currpos.y() - y
    # qp.drawEllipse(x, y, w, h)
    
    # Paint existing shapes
    for col in self.shapes.keys():
        if col is not self.activecolor or deleteshape:
            start = self.shapes[col]['start']
            end = self.shapes[col]['end']
            if start is not None and end is not None:
                p = QPen(QColor(*self.shapes[col]['color']))
                qp.setPen(p)
                qp.drawRect(QRect(start, end))

    # End the QPainter event otherwise the GUI will crash
    qp.end()
    # Show the drawn shapes on the drawing canvas
    self.drawCanvas.setPixmap(pmap)
        
def moveShapes(self):
    pass

# =============================================================================
# FUNCTIONS FOR NOTEPAD
# =============================================================================

def saveNotes(self):
    timestamp = time.strftime("%Y-%m-%d %I_%M_%S %p")
    filename = f'{self.sample} notes {timestamp}.txt'
    filepath = os.path.join(self.activepath, filename)
    with open(filepath, 'w+') as f:
        f.write(str(self.noteEntry.toPlainText()))
    self.mainstatus.setText(f'Saved notes as {filename}')

def clearNotes(self):
    reply = QMessageBox.question(self, 
                'Caution', 
                'Are you sure you want to clear the current notes?',
                QMessageBox.Yes, QMessageBox.No)
    if reply == QMessageBox.Yes:
        self.noteEntry.clear()

# =============================================================================
# FUNCTIONS FOR STOPWATCH AND TIMER
# =============================================================================

def runStopwatch(self):
    pass

def clearStopwatch(self):
    pass

def changeTime(self):
    pass

def runTimer(self):
    pass
    
def resetTimer(self):
    pass

# =============================================================================
# FUNCTIONS FOR UPDATING THE STATUSBAR
# =============================================================================

def showSerial(self):
    if self.camtype == 'FLIR':
        try:
            sn = self.cam.GetUniqueID()
            self.serialstatus.setText('SN: {}'.format(sn))
        except:
            pass
    else:
        self.serialstatus.setText('')

