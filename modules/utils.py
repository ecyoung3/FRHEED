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
# This module is used to set or change the base directory for FRHEED.
#
# =============================================================================

import os
import configparser
import pathvalidate
import threading
import multiprocessing as mupro
from PyQt5 import QtWidgets

from . import utils

def getConfig(configname: str = 'config.ini'):
    working_dir = os.getcwd() # get the current working directory that this script is running from
    config_path = os.path.join(working_dir, configname)
    if not os.path.exists(config_path):
        config_default = """
[Default]
camera_type = 
path = 
colormap = gist_gray
user = Default
sample = Default
flir_gamma = 0.6
flir_blacklevel = 0.0
flir_gain = 25.0
flir_exposure = 3500
usb_exposure = -4

[Profile 1]
profile_name = Profile 1
colormap = gist_gray
inverted = False
usb_exposure = -4
flir_exposure = 5000
flir_gamma = 0.6
flir_blacklevel = 0.0
flir_gain = 25.0

[Profile 2]
profile_name = Profile 2
colormap = gist_gray
inverted = False
usb_exposure = -4
flir_exposure = 5000
flir_gamma = 0.6
flir_blacklevel = 0.0
flir_gain = 25.0

[Profile 3]
profile_name = Profile 3
colormap = gist_gray
inverted = False
usb_exposure = -4
flir_exposure = 5000
flir_gamma = 0.6
flir_blacklevel = 0.0
flir_gain = 25.0
"""
        with open(config_path, 'x') as c:
            c.write(config_default)
    config = configparser.ConfigParser()
    config.read(config_path)
    return config_path, config

def setBasepath(parent, change: bool = False):
    configfile, config = getConfig()
    try:
        basepath = config['Default']['path']
        user = config['Default']['user']
        sample = config['Default']['sample']
    except:
        print('Config options not found.')
    try:
        if not os.path.exists(basepath) or change:
            QtWidgets.QMessageBox.warning(parent, 'Notice', 'Please select a base directory for saving files.')
            path = QtWidgets.QFileDialog.getExistingDirectory(parent, 'Select Save Directory')  # open file location dialog
            if path != "" and pathvalidate.is_valid_filepath(path, platform='Windows'):
                config['Default']['path'] = path
    except:
        QtWidgets.QMessageBox.warning(parent, 'Error', 'The config file appears to be missing the [Default][pathset] entry.')
    
    # Set base path to config
    user, sample = config['Default']['user'], config['Default']['sample']
    userpath = os.path.join(path, user, '')
    samplepath = os.path.join(userpath, sample, '')
    if not os.path.exists(userpath):
        setUser(parent)
    if not os.path.exists(samplepath):
        setSample(parent)
    with open(configfile, 'w') as cfg:  # update the config file
        config.write(cfg)
        print('Config file path locations updated.')

def setUser(parent):
    configfile, config = getConfig()
    basepath = config['Default']['path']
    if not os.path.exists(basepath):
        basepath = setBasepath(parent)
    entry, accepted = QtWidgets.QInputDialog().getText(parent, 'Change User', 'Enter user name:')
    testpath = os.path.join(basepath, entry, '')
    if accepted and entry != '' and pathvalidate.is_valid_filepath(testpath, platform='Windows'):
        userpath = testpath
    elif accepted:
        QtWidgets.QMessageBox.warning(parent, 'Alert', 'User name contains invalid characters for folder creation.')
        setUser(parent)
    else:
        return
    if not os.path.exists(userpath):
        os.makedirs(userpath)
    config['Default']['user'] = entry
    with open(configfile, 'w') as cfg:
        config.write(cfg)

def setSample(parent):
    configfile, config = getConfig()
    basepath = config['Default']['path']
    user = config['Default']['user']
    userpath = os.path.join(basepath, user, '')
    if not os.path.exists(basepath):
        basepath = setBasepath(parent)
    if not os.path.exists(userpath):
        setUser(parent)
    entry, accepted = QtWidgets.QInputDialog().getText(parent, 'Change Sample', 'Enter sample name:')
    testpath = os.path.join(userpath, entry, '')
    if accepted and entry != '' and pathvalidate.is_valid_filepath(testpath, platform='Windows'):
        samplepath = testpath
    elif accepted:
        QtWidgets.QMessageBox.warning(parent, 'Alert', 'Sample name contains invalid characters for folder creation.')
        setSample(parent)
    else:
        return
    if not os.path.exists(samplepath):
        os.makedirs(samplepath)
    config['Default']['sample'] = entry
    with open(configfile, 'w') as cfg:
        config.write(cfg)
        
# Open the current save directory
def openDirectory():
    configfile, config = utils.getConfig()
    base = config['Default']['path']
    user = config['Default']['user']
    sample = config['Default']['sample']
    path = os.path.join(base, user, sample, '')
    p = os.path.realpath(path)
    os.startfile(p)  # startfile only works on Windows

def makeThread(func, args):
    p = threading.Thread(target=func, args=args)  # again, fps isn't actually used but leave it
    return p

def convertExposure(level: int):
    lvl = str(level)
    # USB exposure level on the left, estimated exposure time on the right (in ms)
    # Source: http://www.principiaprogramatica.com/2017/06/11/setting-manual-exposure-in-opencv/
    realtimes = {
        '-1':   640,
        '-2':   320,
        '-3':   160,
        '-4':   80,
        '-5':   40,
        '-6':   20,
        '-7':   10,
        '-8':   5,
        '-9':   2.5,
        '-10':  1.25,
        '-11':  0.650,
        '-12':  0.312,
        '-13':  0.150,
        }
    if lvl in realtimes.keys():
        exptime = realtimes[lvl]
        
    else:
        exptime = lvl
        
    return exptime