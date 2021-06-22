# =============================================================================
# Copyright (c) 2001-2019 FLIR Systems, Inc. All Rights Reserved.
#
# This software is the confidential and proprietary information of FLIR
# Integrated Imaging Solutions, Inc. ("Confidential Information"). You
# shall not disclose such Confidential Information and shall use it only in
# accordance with the terms of the license agreement you entered into
# with FLIR Integrated Imaging Solutions, Inc. (FLIR).
#
# FLIR MAKES NO REPRESENTATIONS OR WARRANTIES ABOUT THE SUITABILITY OF THE
# SOFTWARE, EITHER EXPRESSED OR IMPLIED, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
# PURPOSE, OR NON-INFRINGEMENT. FLIR SHALL NOT BE LIABLE FOR ANY DAMAGES
# SUFFERED BY LICENSEE AS A RESULT OF USING, MODIFYING OR DISTRIBUTING
# THIS SOFTWARE OR ITS DERIVATIVES.
# =============================================================================
#
# HighDynamicRange.py
# This example shows how to set High Dynamic Range (HDR) if it is available on the camera.

import PySpin
import os
import sys

NUM_IMAGES = 4  # number of images to grab

K_HDR_SHUTTER1 = 1000   # us
K_HDR_SHUTTER2 = 5000
K_HDR_SHUTTER3 = 15000
K_HDR_SHUTTER4 = 30000

K_HDR_GAIN1 = 0   # dB
K_HDR_GAIN2 = 5
K_HDR_GAIN3 = 10
K_HDR_GAIN4 = 15


def print_device_info(nodemap):
    """
    Helper for outputting camera information

    :param nodemap: Transport layer device nodemap.
    :type INodeMap
    :returns: True if successful, False otherwise.
    :rtype: bool
    """

    print('*** DEVICE INFORMATION ***')

    try:
        node_device_information = PySpin.CCategoryPtr(nodemap.GetNode('DeviceControl'))

        if PySpin.IsAvailable(node_device_information) and PySpin.IsReadable(node_device_information):
            features = node_device_information.GetFeatures()
            for feature in features:
                node_feature = PySpin.CValuePtr(feature)
                print('%s: %s' % (node_feature.GetName(),
                                  node_feature.ToString() if PySpin.IsReadable(node_feature) else 'Node not readable'))

        else:
            print('Device control information not available.')

    except PySpin.SpinnakerException as ex:
        print('Error: %s' % ex)
        return False

    return True

def check_node_accessibility(node):
    """
    Helper for checking GenICam node accessibility

    :param node: GenICam node being checked
    :type node: CNodePtr
    :return: True if accessible, False otherwise
    :rtype: bool
    """

    return PySpin.IsAvailable(node) and (PySpin.IsReadable(node) or PySpin.IsWritable(node))

def toggle_hdr_mode(nodemap, hdr_on):
    """
    Helper for toggling HDR mode on camera

    :param nodemap: Transport layer device nodemap.
    :type: INodeMap
    :param hdr_on: True if want to turn hdr mode on, False otherwise.
    :type hdr_on: bool
    :return: True if successful, False otherwise.
    :rtype: bool
    """

    node_hdr_enabled = PySpin.CBooleanPtr(nodemap.GetNode("PGR_HDRModeEnabled"))

    if check_node_accessibility(node_hdr_enabled):
        node_hdr_enabled.SetValue(hdr_on)
    else:
        return False

    print('HDR mode turned to', hdr_on)

    return True

def initialize_hdr_images(nodemap):
    """
    Helper for initializing HDR images

    :param nodemap: Transport layer device nodemap.
    :type: INodeMap
    :return: True if successful, False otherwise.
    :rtype: bool
    """

    hdr_image_selector = PySpin.CEnumerationPtr(nodemap.GetNode("PGR_HDRImageSelector"))
    hdr_exposure_abs = PySpin.CFloatPtr(nodemap.GetNode("PGR_HDR_ExposureTimeAbs"))
    hdr_gain_abs = PySpin.CFloatPtr(nodemap.GetNode("PGR_HDR_GainAbs"))

    if not check_node_accessibility(hdr_image_selector):
        return False
    if not check_node_accessibility(hdr_exposure_abs):
        return False
    if not check_node_accessibility(hdr_gain_abs):
        return False

    # Configure Image1
    hdr_image_selector.SetIntValue(hdr_image_selector.GetEntryByName("Image1").GetValue())
    hdr_exposure_abs.SetValue(K_HDR_SHUTTER1)
    hdr_gain_abs.SetValue(K_HDR_GAIN1)
    print('Initialized HDR Image1...')

    # Configure Image2
    hdr_image_selector.SetIntValue(hdr_image_selector.GetEntryByName("Image2").GetValue())
    hdr_exposure_abs.SetValue(K_HDR_SHUTTER2)
    hdr_gain_abs.SetValue(K_HDR_GAIN2)
    print('Initialized HDR Image2...')

    # Configure Image3
    hdr_image_selector.SetIntValue(hdr_image_selector.GetEntryByName("Image3").GetValue())
    hdr_exposure_abs.SetValue(K_HDR_SHUTTER3)
    hdr_gain_abs.SetValue(K_HDR_GAIN3)
    print('Initialized HDR Image3...')

    # Configure Image4
    hdr_image_selector.SetIntValue(hdr_image_selector.GetEntryByName("Image4").GetValue())
    hdr_exposure_abs.SetValue(K_HDR_SHUTTER4)
    hdr_gain_abs.SetValue(K_HDR_GAIN4)
    print('Initialized HDR Image4...')

    return True

def run_single_camera(cam):
    """
    Helper for running example on single camera

    :param cam: Camera to run on.
    :type cam: CameraPtr
    :return: True if successful, False otherwise.
    :rtype: bool
    """
    try:
        result = True

        # Initialize camera
        cam.Init()

        # Get GenICam NodeMap info from camera
        nodemap = cam.GetNodeMap()

        # Get camera information through NodeMap
        print_device_info(nodemap)

        # Verify whether HDR is supported on this device
        node_hdr_enabled = PySpin.CBooleanPtr(nodemap.GetNode("PGR_HDRModeEnabled"))
        if not PySpin.IsAvailable(node_hdr_enabled):
            print('HDR is not supported! Exiting...')
            return True

        # HDR needs to be enabled prior to configure individual HDR images
        toggle_hdr_mode(nodemap, True)

        if not initialize_hdr_images(nodemap):
            print('Error configuring HDR image! Exiting...')
            return False

        # Retrieve Device ID
        device_id = cam.GetTLDeviceNodeMap().GetNode("DeviceID")

        # Begin capturing images
        print('Starting grabbing images...')
        cam.BeginAcquisition()

        for i in range(NUM_IMAGES):
            try:
                # Retrieve the next received image
                raw_image = cam.GetNextImage(1000)
                width = raw_image.GetWidth()
                height = raw_image.GetHeight()
                print('Grabbed image %d, width = %d, height = %d' % (i, width, height))

                # Convert image to Mono8
                converted_image = raw_image.Convert(PySpin.PixelFormat_Mono8)

                # Create a unique filename
                filename = 'HighDynamicRange-%s-%d.jpg' % (device_id, i)

                # Save image
                converted_image.Save(filename)

                # Image need to be released after use
                raw_image.Release()

            except PySpin.SpinnakerException as ex:
                print('Error Retrieving Image: %s' % ex)
                result = False
                continue

        # End capturing of images
        cam.EndAcquisition()

    except PySpin.SpinnakerException as ex:
        print('Error: %s' % ex)
        result = False

    print()

    return result

def main():
    """
    Example entry point; please see Enumeration example for more in-depth
    comments on preparing and cleaning up the system.

    :return: True if successful, False otherwise.
    :rtype: bool
    """

    # Since this application saves images in the current folder
    # we must ensure that we have permission to write to this folder.
    # If we do not have permission, fail right away.
    try:
        test_file = open('test.txt', 'w+')
    except IOError:
        print('Unable to write to current directory. Please check permissions.')
        input('Press Enter to exit...')
        return False

    test_file.close()
    os.remove(test_file.name)

    result = True

    # Retrieve singleton reference to system object
    system = PySpin.System.GetInstance()

    # Get current library version
    version = system.GetLibraryVersion()
    print('Library version: %d.%d.%d.%d' % (version.major, version.minor, version.type, version.build))

    # Retrieve list of cameras from the system
    cam_list = system.GetCameras()

    num_cameras = cam_list.GetSize()

    print('Number of cameras detected: %d' % num_cameras)

    # Finish if there are no cameras
    if num_cameras == 0:

        # Clear camera list before releasing system
        cam_list.Clear()

        # Release system instance
        system.ReleaseInstance()

        print('Not enough cameras!')
        input('Done! Press Enter to exit...')
        return False

    # Run example on each camera
    for cam in cam_list:
        result &= run_single_camera(cam)

    # Release reference to camera
    # NOTE: Unlike the C++ examples, we cannot rely on pointer objects being automatically
    # cleaned up when going out of scope.
    # The usage of del is preferred to assigning the variable to None.
    del cam

    # Clear camera list before releasing system
    cam_list.Clear()

    # Release system instance
    system.ReleaseInstance()

    input('Done! Press Enter to exit...')
    return result

if __name__ == '__main__':
    if main():
        sys.exit(0)
    else:
        sys.exit(1)
