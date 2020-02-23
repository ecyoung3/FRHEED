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
# This module is used for detecting and connecting to different cameras.
#
# =============================================================================

import sys
import os.path
import configparser
import PySpin
import cv2
from PyQt5 import QtWidgets

from . import utils, build

try:
    from pymba import Vimba, Frame # for connecting to Allied Vision Stingray firewire cameras
    pymba_imported = True
except Exception as ex:
    pymba_imported = False
    print('ERROR: {}'.format(ex))

# TODO update the config to have sub-dicts for each camera type default

class FLIR:
    def __init__(self):
        super().__init__() 
        # NOTE: __init__ gets called every time a function from the FLIR() class runs
        # That means streaming will be very slow if there are computationally intense
        # functions in this section.
            
    # For buffer handling mode information, see https://www.flir.com/support-center/iis/machine-vision/application-note/understanding-buffer-handling/
    # NewestOnly is most likely the best option 99% of the time
    def connectCam(self, mode = 'NewestOnly'):
        result = True # return this if the function completes successfully
        # Importing config options
        self.configfile, self.config = utils.getConfig()
        try:
            flir_exposure = float(self.config['Default']['flir_exposure'])
            gamma = float(self.config['Default']['flir_gamma'])
            blacklevel = float(self.config['Default']['flir_blacklevel'])
            gain = float(self.config['Default']['flir_gain'])
        except:
            QtWidgets.QMessageBox.warning(None, 'Error', 'Config options not found or invalid options entered.')
            result = False
        self.system = PySpin.System.GetInstance()  # start new instance; returns PySpin.SystemPtr() object (so PySpin.SystemPtr is equivalent to system)
        self.cam_list = self.system.GetCameras()  # get list of cameras
        self.num_cameras = self.cam_list.GetSize() # number of cameras found
        if self.num_cameras == 0:
            print('No FLIR cameras found. Please check the connection, or troubleshoot with PySpin.')
            self.cam_list.Clear() # clear camera list before releasing system
            self.system.ReleaseInstance() # release system instance
            return None, None, None, None
        for cam in self.cam_list:
            nodemap_tldevice = cam.GetTLDeviceNodeMap()
            node_device_serial_number = PySpin.CStringPtr(nodemap_tldevice.GetNode('DeviceSerialNumber'))
            self.serial_number = node_device_serial_number.GetValue()
        if PySpin.IsAvailable(node_device_serial_number) and PySpin.IsReadable(node_device_serial_number):
            self.cam = self.cam_list.GetBySerial(self.serial_number) # get the specific camera
        else:
            QtWidgets.QMessageBox.warning(None, 'Error', 'Failed to connect to a FLIR camera.')  
        self.cam.Init()
        # Set exposure manually, if possible
        if self.cam.ExposureAuto.GetAccessMode() != PySpin.RW:
            QtWidgets.QMessageBox.warning(None, 'Error', 'Failed to disable automatic exposure.\nFRHEED will exit now.')
            result = False
        self.cam.ExposureAuto.SetValue(PySpin.ExposureAuto_Off) # disable auto exposure
        min_exposure, max_exposure = self.cam.ExposureTime.GetMin(), self.cam.ExposureTime.GetMax()
        if flir_exposure < max_exposure and flir_exposure > min_exposure:
            self.cam.ExposureTime.SetValue(flir_exposure) # set exposure time in microseconds
        else:
            self.cam.ExposureTime.SetValue(10000.0)
        # Set gamma manually
        self.cam.GammaEnabled = True
        self.cam.Gamma.SetValue(gamma)
        # Set black level manually
        self.cam.BlackLevel.SetValue(blacklevel)
        # Set frame rate manually and retrieve actual frame rate. See PySpin examples for reference.
        if self.cam.IsInitialized():
            nodemap = self.cam.GetNodeMap() # get nodemap from which camera options are read
        else:
            QtWidgets.QMessageBox.warning(None, 'Error', 'Failed to generate device nodemap.\nFRHEED will exit now.')
            result = False
        # Set gain manually
        if self.cam.GainAuto.GetAccessMode() != PySpin.RW:
            QtWidgets.QMessageBox.warning(None, 'Error', 'Failed to disable automatic gain.\nFRHEED will exit now.')
            result = False
        self.cam.GainAuto.SetValue(PySpin.GainAuto_Off)
        self.cam.Gain.SetValue(gain)
        # Set acquisition mode to continuous
        node_acquisition_mode = PySpin.CEnumerationPtr(nodemap.GetNode('AcquisitionMode'))
        if not PySpin.IsAvailable(node_acquisition_mode) or not PySpin.IsWritable(node_acquisition_mode):
            QtWidgets.QMessageBox.warning(None, 'Error', 'Failed to retrieve node for acquisition mode.\nFRHEED will exit now.')
            result = False
        node_acquisition_mode_continuous = node_acquisition_mode.GetEntryByName('Continuous')
        if not PySpin.IsAvailable(node_acquisition_mode_continuous) or not PySpin.IsReadable(node_acquisition_mode_continuous):
            QtWidgets.QMessageBox.warning(None, 'Error', 'Failed to set acquisition mode to continuous.\nFRHEED will exit now.')
            result = False
        acquisition_mode_continuous = node_acquisition_mode_continuous.GetValue() # get continuous acquisition mode
        node_acquisition_mode.SetIntValue(acquisition_mode_continuous) # set continuous acquisition mode
        # Set buffer handling mode
        # THIS SECTION IS IMPORTANT. Changing the buffer mode can have a dramatic effect on performance. See the "BufferHandling.Py" example for details on syntax. Modes can be tested in PySpin.
        s_node_map = self.cam.GetTLStreamNodeMap() # get stream parameters device nodemap. see BufferHandling.Py example for reference
        handling_mode = PySpin.CEnumerationPtr(s_node_map.GetNode('StreamBufferHandlingMode')) # find the setting for buffer handling mode so it can be changed
        if not PySpin.IsAvailable(handling_mode) or not PySpin.IsWritable(handling_mode):
            QtWidgets.QMessageBox.warning(None, 'Error', 'Failed to retrieve node for buffer handling mode.\nFRHEED will exit now.')
            result = False
        handling_mode_entry = handling_mode.GetEntryByName(mode) # get valid handling mode so it can be set
        if not PySpin.IsAvailable(handling_mode_entry) or not PySpin.IsReadable(handling_mode_entry):
            QtWidgets.QMessageBox.warning(None, 'Error', 'Failed to set buffer handling mode to Newest First.\nFRHEED will exit now.')
            result = False
        handling_mode.SetIntValue(handling_mode_entry.GetValue()) # actually set the handling mode to whatever is chosen
        
        ''' THE NEXT SECTION IS OPTIONAL '''
        # stream_buffer_count_mode = PySpin.CEnumerationPtr(s_node_map.GetNode('StreamBufferCountMode')) # get the current buffer count mode
        # if not PySpin.IsAvailable(stream_buffer_count_mode) or not PySpin.IsWritable(stream_buffer_count_mode):
        #     QtWidgets.QMessageBox.warning(None, 'Error', 'Failed to retrieve node for setting buffer count.\nFRHEED will exit now.')
        #     result = False
        # stream_buffer_count_mode_manual = PySpin.CEnumEntryPtr(stream_buffer_count_mode.GetEntryByName('Manual'))
        # if not PySpin.IsAvailable(stream_buffer_count_mode_manual) or not PySpin.IsReadable(stream_buffer_count_mode_manual):
        #     QtWidgets.QMessageBox.warning(None, 'Error', 'Failed to set buffer count mode to manual.\nFRHEED will exit now.')
        #     result = False
        # stream_buffer_count_mode.SetIntValue(stream_buffer_count_mode_manual.GetValue())
        # buffer_count = PySpin.CIntegerPtr(s_node_map.GetNode('StreamBufferCountManual'))
        # if not PySpin.IsAvailable(buffer_count) or not PySpin.IsWritable(buffer_count):
        #     QtWidgets.QMessageBox.warning(None, 'Error', 'Failed to set buffer count.\nFRHEED will exit now.')
        #     result = False
        # buffer_count.SetValue(300) # max value is 369. default is 10

        return result, self.system, self.cam_list, self.cam
            
    def stream(self, cam, parent):
        img = None
        if cam.IsValid() and not cam.IsStreaming():
            if not cam.IsInitialized():
                cam.Init()
            try:
                cam.BeginAcquisition()
                print('Started streaming from FLIR camera.')
            except:
                pass
        if cam.IsStreaming():
            image_result = cam.GetNextImage()
            try:
                # Check if the amount of data received is as expected (full frame)
                if not image_result.IsIncomplete():
                    img = image_result.GetNDArray()
                    image_result.Release()
                    return img
                
                # Keep track of dropped/incomplete frames
                elif image_result.IsIncomplete():
                    parent.droppedframes += 1
                    # For whatever reason, .Release() doesn't seem to clear the buffer
                    # properly, and after enough dropped frame accumulate, the stream
                    # will begin to lag. Restarting the acquisition every 10 dropped
                    # frames flushes the buffer and makes sure the stream doesn't lag.
                    if parent.droppedframes % 3 == 0:
                        cam.EndAcquisition()
                        cam.BeginAcquisition()
                    
                # Release the image to clear it from the buffer (supposedly)
                image_result.Release()
            except:
                pass
        return img

    def readFPS(self, cam):
        display_fps = ''
        if cam.IsInitialized():
            nodemap = cam.GetNodeMap() # get nodemap from which camera options are read
            node_acquisition_framerate = PySpin.CFloatPtr(nodemap.GetNode('AcquisitionFrameRate'))
            display_fps = '{:.2f}'.format(node_acquisition_framerate.GetValue())
            return display_fps
        return display_fps
        
    def select(self, cam, parent):
        parent.cam = cam
        parent.camtype = 'FLIR'
        build.camsettings(parent)
        configfile, config = utils.getConfig()
        config['Default']['camera_type'] = 'FLIR'
        with open(configfile, 'w') as c:
            config.write(c)
            print('Updated config file cameratype.')
            
    def disconnect(self, system):
        if system is not None:
            cam_list = system.GetCameras()
            num_cameras = cam_list.GetSize()
            if num_cameras > 0:
                for cam in cam_list:
                    if cam.IsStreaming():
                        image_result = cam.GetNextImage()
                        image_result.Release()
                        cam.EndAcquisition()
                    if cam.IsInitialized():
                        cam.DeInit()
                    del cam
                cam_list.Clear()
                del cam_list
            else:
                cam_list.Clear()
                system.ReleaseInstance()
                return
            try:
                system.ReleaseInstance()
            except:
                del system
        else:
            return
        print('Released FLIR camera.')
        
class USB:
    def __init__(self):
        super().__init__()
            
    def connectCam(self):
        configfile, config = utils.getConfig()
        try:
            cam = cv2.VideoCapture(0)
        except:
            print('No USB cameras found.')
            cam = None
        try:
            exposure = int(config['Default']['usb_exposure'])
        except:
            QtWidgets.QMessageBox.warning(None, 'Error', 'Config option not found or has invalid value.')
        if cam is not None:
            if not cam.isOpened():
                print('No USB cameras found.')
        try:
            if -13 <= exposure <= -1:
                cam.set(cv2.CAP_PROP_EXPOSURE, exposure)  # set camera exposure
            else:
                exposure = -5
                cam.set(cv2.CAP_PROP_EXPOSURE, exposure)  # set camera exposure
        except:
            QtWidgets.QMessageBox.warning(None, 'Error', 'Failed to set USB camera exposure to {}'.format(exposure))
        return cam
     
    def stream(self, cam, parent):
        img = None
        if cam is not None and cam.isOpened():
            grabbed, img = cam.read()  # read frame from webcam; grabbed = True if the frame isn't empty
            if grabbed:  # make sure the frame was actually collected
                img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)  # convert webcam to grayscale
            else:
                print('Skipped frame...')
        else: # give an error if the camera isn't detected
            print('ERROR: No USB cameras connected.')
        return img
        
    def select(self, cam, parent):
        parent.cam = cam
        parent.camtype = 'USB'
        build.camsettings(parent)
        configfile, config = utils.getConfig()
        config['Default']['camera_type'] = 'USB'
        with open(configfile, 'w') as c:
            config.write(c)
            print('Updated config file cameratype.')

    def disconnect(self):
        try:
            cam = cv2.VideoCapture(0)
        except:
            cam = None
        if not cam.isOpened() or cam is None:
            print('No USB cameras connected that need releasing.')
        else:
            cam.release()
            print('Released USB camera.')

class selectionDialog(QtWidgets.QDialog):  
    def __init__(self, parent):
        super(selectionDialog, self).__init__(parent)
        self.parent = parent
        
    def chooseCamera(self, system, quitting:bool=False):
        self.configfile, self.config = utils.getConfig()
        self.dialog = QtWidgets.QDialog(self.parent) # dialog will inherit stylesheet from parent widget (FRHEED main UI)
        self.dialog.setFixedSize(400, 200)
        self.dialog.setStyleSheet("""
            QPushButton {background-color: qlineargradient(x1: 0.5, y1: 1.0, x2: 0.5, y2: 0.0, stop: 1.0 rgb(68, 86, 100), 
                0.0 rgb(44, 55, 64)); font: 14pt "Bahnschrift SemiLight"; color: white; border-radius: 3px;
                border: 1px solid rgba(80, 95, 105, 255); font-weight: bold; padding: 10px;} 
            QPushButton:hover:!disabled {background: qlineargradient(x1: 0.5, y1: 1.0, x2: 0.5, y2: 0.0, stop: 1.0 rgb(68, 86, 100), 
                0.0 rgb(44, 55, 64)); padding-bottom: 11px; padding-top: 9px; border: 1px solid rgb(0, 167, 209)}
            QPushButton:disabled {color: rgba(80, 95, 105, 150)}
            """)    
        self.dialog.setWindowTitle('Select Camera')  # set title of window
        self.dialog.verticalLayout = QtWidgets.QVBoxLayout(self.dialog)  # create vertical layout for window
        # Add button that says 'USB'
        self.dialog.usbButton = QtWidgets.QPushButton()  # create first button
        self.dialog.usbButton.setDefault
        self.dialog.flirButton = QtWidgets.QPushButton()  # create second button
        # Check for USB cameras
        usb_cam = USB().connectCam()
        # Check for FLIR cameras
        if system is not None:
            cam_list = system.GetCameras()  # get list of cameras
            for flir_cam in cam_list:
                nodemap_tldevice = flir_cam.GetTLDeviceNodeMap()
                node_device_serial_number = PySpin.CStringPtr(nodemap_tldevice.GetNode('DeviceSerialNumber'))
                sn = node_device_serial_number.GetValue()
        else:
            _, system, cam_list, flir_cam = FLIR().connectCam()
        if usb_cam.isOpened():
            self.dialog.usbButton.setText('Generic USB Camera')  # set button text
        else:
            self.dialog.usbButton.setText('No USB cameras detected')
            self.dialog.usbButton.setEnabled(False)
        try:
            if cam_list.GetSize() > 0:
                self.dialog.flirButton.setText('FLIR GigE Camera\nSerial #{}'.format(sn))  # set button text
            else:
                self.dialog.flirButton.setText('No FLIR cameras detected')
                self.dialog.flirButton.setEnabled(False)
        except:
            self.dialog.flirButton.setText('No FLIR cameras detected')
            self.dialog.flirButton.setEnabled(False)
        # Add buttons to the layout
        self.dialog.verticalLayout.addWidget(self.dialog.usbButton)  # add the first button to the layout, below the text
        self.dialog.verticalLayout.addWidget(self.dialog.flirButton)  # add second button to layout, below the first button
        # Define what happens when the buttons are clicked
        self.dialog.usbButton.clicked.connect(lambda: USB().select(usb_cam, self.parent))  # NOTE: use lambda because clicked.connect() expects a callable function. will get 'NoneType' error otherwise
        self.dialog.usbButton.clicked.connect(lambda: FLIR().disconnect(system))  # disconnects FLIR camera if USB is selected
        self.dialog.usbButton.clicked.connect(self.dialog.accept) # close self.dialog if button 2 is clicked
        self.dialog.flirButton.clicked.connect(lambda: FLIR().select(flir_cam, self.parent))  # selects FLIR camera
        self.dialog.flirButton.clicked.connect(lambda: USB().disconnect())  # selects FLIR camera
        self.dialog.flirButton.clicked.connect(self.dialog.accept) # close self.dialog if button 2 is clicked
        d = self.dialog.exec_() # execute the dialog window to make it appear
        if d == QtWidgets.QDialog.Rejected:
            if quitting:
                FLIR().disconnect(system)
                USB().disconnect()
                print('Exiting...')
                sys.exit()
            else:
                self.dialog.close()
        if d == QtWidgets.QDialog.Accepted:
            self.dialog.close()
                
# Code for grabbing frames from camera in threaded loop
def grabImage(self):
    img = None
    while self.running:
        if self.camtype == 'FLIR':
            img = FLIR().stream(self.cam, self)
        elif self.camtype == 'USB':
            img = USB().stream(self.cam, self)
        return img
    return img

if pymba_imported:
    class AlliedVision:   
        def connectCam(self):
            result = True
            vimba = Vimba()
            try:
                cam = vimba.camera(0)
                print('Found Allied Vision camera.')
            except Exception as ex:
                print('ERROR: No Allied Vision cameras found.\nException: {}\nAborting...'.format(ex))
                result = False
                return result
            try:
                cam.open()
                print('Allied Vision camera connected.')
            except Exception as ex:
                print('ERROR: Unable to open Allied Vision camera.\nException: {}\nAborting...'.format(ex))
                result = False
            return result

        def stream(self, cam, result: bool, frame: Frame, delay: int = 1):
            result = True
            try:
                cam.arm('Continuous', AlliedVision.display_frame()) # need to add this function
                print('Set Allied Vision acquisition mode to continuous.')
            except Exception as ex:
                print('ERROR: Unable to set Allied Vision acquisition mode to continuous.\nException: {}\nAborting...'.format(ex))
                result = False
            return result
        
        def displayFrame(self, frame: Frame, delay: int = 1, converting: bool = False):
            conversions = {
                'BayerRG8': cv2.COLOR_BAYER_RG2RGB,
                }
            image = frame.buffer_data_numpy()
            if converting:
                try:
                    image = cv2.cvtColor(image, conversions[frame.pixel_format]) # TODO This still needs to be fixed - not sure what the right color conversion is - step is also optional
                    return image
                except KeyError:
                    pass 
            return image
                
        def disconnect(self, cam):
            cam.stop_frame_acquisition()
            cam.disarm()
            cam.close()
            print('Allied Vision camera disconnected successfully.')
            