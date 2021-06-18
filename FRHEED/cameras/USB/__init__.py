# -*- coding: utf-8 -*-
"""
Connecting to USB cameras.
"""

import os
from typing import Union, Optional, List, Tuple
import time
import cv2
import numpy as np

from frheed.cameras import CameraError

# Suppress warning from MSMF backend bug
# https://stackoverflow.com/a/54585850/10342097
os.environ["OPENCV_VIDEOIO_PRIORITY_MSMF"] = "0"

_DEBUG = (__name__ == "__main__")

# Get non-platform-specific capture properties (0 < id < 50)
_CAP_PROPS = [prop for prop in dir(cv2) if prop.startswith("CAP_PROP")
              and getattr(cv2, prop, 1000) < 50]

# Editable camera settings to show
_GUI_SETTINGS = {
    "CAP_PROP_BRIGHTNESS":      "Brightness",
    "CAP_PROP_CONTRAST":        "Contrast",
    "CAP_PROP_SATURATION":      "Saturation",
    "CAP_PROP_GAIN":            "Gain",
    "CAP_PROP_EXPOSURE":        "Exposure",
    }

# Read-only camera information to show
_GUI_INFO = {
    "CAP_PROP_FRAME_WIDTH":     "Frame Width",
    "CAP_PROP_FRAME_HEIGHT":    "Frame Height",
    "CAP_PROP_TEMPERATURE":     "Temperature",  # TODO: figure out units
    
    }

# Backend for cameras
_DEFAULT_BACKEND = cv2.CAP_DSHOW  # cv2.CAP_DSHOW or cv2.CAP_MSMF

def list_cameras() -> List[int]:
    """
    Get list of indices of available USB cameras.

    Returns
    -------
    List[int]
        List of indices of available USB cameras.

    """
    
    # Add camera indices until list is exhausted
    cam_list = []
    
    for idx in range(100):
        cap = cv2.VideoCapture(idx, _DEFAULT_BACKEND)
        if not cap.read()[0]:
            break
        else:
            cam_list.append(idx)
        cap.release()
    
    # This seems to help fix FPS when using backend CAP_DSHOW
    cv2.destroyAllWindows()
        
    return cam_list

def get_available_cameras() -> dict:
    """ Get available cameras as a dictionary of {source: name}. """
    cams = list_cameras()
    available = {}
    
    for src in cams:
        try:
            with UsbCamera(src=src) as cam:
                if cam.initialized:
                    available[src] = str(cam)
                else:
                    print(f"USB camera {src} is not available")
        except CameraError:
            print("No USB cameras detected")
            
    return available


class UsbCamera:
    """
    A class used to encapsulate a cv2.VideoCapture camera.
    
    Attributes
    ----------
    cam : cv2.VideoCapture
    running : bool
        True if acquiring images
    camera_attributes : dictionary
        Contains all of the non-platform-specific cv2.CAP_PROP_... attributes
    camera_methods : dictionary
        Contains all of the camera methods
    
    """
    
    _cap_props = {
        "CAP_PROP_POS_MSEC":         "Current position of the video file in milliseconds.",
        "CAP_PROP_POS_FRAMES":       "0-based index of the frame to be decoded/captured next.",
        "CAP_PROP_POS_AVI_RATIO":    "Relative position of the video file: 0 - start, 1 - end.",
        "CAP_PROP_FRAME_WIDTH":      "Width of the frames in the video stream.",
        "CAP_PROP_FRAME_HEIGHT":     "Height of the frames in the video stream.",
        "CAP_PROP_FPS":              "Frame rate.",
        "CAP_PROP_FOURCC":           "4-character code of codec.",
        "CAP_PROP_FRAME_COUNT":      "Number of frames in the video file.",
        "CAP_PROP_FORMAT":           "Format of the Mat objects returned by retrieve().",
        "CAP_PROP_MODE":             "Backend-specific value indicating the current capture mode.",
        "CAP_PROP_BRIGHTNESS":       "Brightness of the image (only for cameras).",
        "CAP_PROP_CONTRAST":         "Contrast of the image (only for cameras).",
        "CAP_PROP_SATURATION":       "Saturation of the image (only for cameras).",
        "CAP_PROP_HUE":              "Hue of the image (only for cameras).",
        "CAP_PROP_GAIN":             "Gain of the image (only for cameras).",
        "CAP_PROP_EXPOSURE":         "Exposure (only for cameras).",
        "CAP_PROP_CONVERT_RGB":      "Boolean flags indicating whether images should be converted to RGB.",
        "CAP_PROP_RECTIFICATION":    "Rectification flag for stereo cameras.",
        "CAP_PROP_ISO_SPEED":        "The ISO speed of the camera.",
        "CAP_PROP_BUFFERSIZE":       "Amount of frames stored in internal buffer memory.",
        }
    
    def __init__(
            self, 
            src: Union[int, str] = 0, 
            lock: bool = False,
            backend: Optional[int] = _DEFAULT_BACKEND # cv2.CAP_DSHOW
            ):
        """
        Parameters
        ----------
        src : Union[int, str], optional
            Camera source as an index or path to video file. The default is 0.
        lock : bool, optional
            If True, attribute access is locked down; after the camera is
            initialized, attempts to set new attributes will raise an error. 
            The default is True.
        backend : Optional[int], optional
            Camera backend. The default is cv2.CAP_DSHOW.
        """
        super().__setattr__("camera_attributes", {})
        super().__setattr__("camera_methods", {})
        super().__setattr__("lock", lock)
        
        cam_list = list_cameras()
        if _DEBUG:
            print(f"Found {len(cam_list)} USB camera(s)")
        
        if not cam_list:
            raise CameraError("No USB cameras detected.")
        
        self._src_type = type(src)
        self._src = src
        
        # Initialize the camera, either by index or filepath (to video)
        if backend is not None:
            self._cam = cv2.VideoCapture(src, backend)
        else:
            self._cam = cv2.VideoCapture(src)
            
        # Get camera attributes
        for attr in _CAP_PROPS:
            self.camera_attributes[attr] = {}
            if attr in self._cap_props:
                self.camera_attributes[attr]["description"] = self._cap_props[attr]
        
        # Other attributes which may be accessed later
        self._running = True  # camera is running as soon as you connect to it
        self._frame_times = []
        self._incomplete_image_count = 0
        
    def __getattr__(self, attr: str) -> object:
        # Add this in so @property decorator works as expected
        if attr in self.__dict__:
            return self.__dict__[attr]
        
        elif attr in self.camera_attributes:
            propId = getattr(cv2, attr, None)
            if propId is None:
                raise AttributeError(f"{attr} is not a valid propId")
            return self.cam.get(propId)
        
        else:
            raise AttributeError(attr)
            
    def __setattr__(self, attr: str, val: object) -> None:
        if attr in self.camera_attributes:
            propId = getattr(cv2, attr, None)
            if propId is None:
                raise AttributeError(f"Unknown propId '{attr}'")
                
            # In order to change CAP_PROP_EXPOSURE, it has to be set to 0.25
            # first in order to enable manual exposure
            # https://github.com/opencv/opencv/issues/9738#issuecomment-346584044
            if propId in ["CAP_PROP_EXPOSURE"]:
                self.cam.set(propId, 0.25)
                
            success = self.cam.set(propId, val)
            result = "succeeded" if success else "failed"
            if _DEBUG or not success:
                print(f"Setting {attr} to {val} {result}")
            
        else:
            if attr == "__class__":
                super().__setattr__(attr, val)
            elif attr not in self.__dict__ and self.lock and self.initialized:
                raise CameraError(f"Unknown property '{attr}'")
            else:
                super().__setattr__(attr, val)
        
    def __enter__(self) -> "UsbCamera":
        self.init()
        return self
    
    def __exit__(self, type, value, traceback) -> None:
        self.close()
        
    def __del__(self) -> None:
        self.close()
        
    def __str__(self) -> str:
        return f"USB (Port {self._src})"
    
    @property
    def name(self) -> str:
        return f"USB{self._src}"
    
    @property
    def camera_type(self) -> str:
        return "USB"
    
    @property
    def cam(self) -> cv2.VideoCapture:
        return self._cam

    @property
    def initialized(self) -> bool:
        return self.cam.isOpened()

    @property
    def running(self) -> bool:
        return self._running
    
    @property
    def incomplete_image_count(self) -> int:
        return self._incomplete_image_count
    
    @property
    def real_fps(self) -> float:
        """ Get the real frames per second (Hz) """
        
        # When not enough frames have been captured
        if len(self._frame_times) <= 1:
            return 0.
        
        # When fewer than 60 frames have been captured in this acquisition
        elif len(self._frame_times) < 60:
            dt = (self._frame_times[-1] - self._frame_times[0])
            return len(self._frame_times) / max(dt, 1)
        
        # Return the average frame time of the last 60 frames
        else:
            return 60 / (self._frame_times[-1] - self._frame_times[-60])
    
    @property
    def width(self) -> int:
        return int(self.CAP_PROP_FRAME_WIDTH)
    
    @property
    def height(self) -> int:
        return int(self.CAP_PROP_FRAME_HEIGHT)
    
    @property
    def shape(self) -> Tuple[int, int]:
        return (self.width, self.height)
    
    def init(self):
        if not self.initialized:
            self.cam.open(self._src)
    
    def start(self, continuous: bool = True) -> None:
        # Initialize the camera
        if not self.initialized:
            self.init()
            
        # Begin acquisition
        self._running = True
        
    def stop(self) -> None:
        self._frame_times = []
        self._incomplete_image_count = 0
        self._running = False
    
    def close(self) -> None:
        self.stop()
        self.cam.release()
        
    def get_array(self, complete_frames_only: bool = False) -> np.ndarray:
        # Grab and retrieve the camera array
        is_complete, array = self.cam.read()
        
        # Increment incomplete image count if full image is not retrieved
        if not is_complete:
            self._incomplete_image_count += 1
            
        # Ensure complete image is returned if option is chosen
        if complete_frames_only and not is_complete:
            return self.get_array(complete_frames_only)
        
        # Store frame time for real FPS calculation
        self._frame_times.append(time.time())
        
        return array
    
    def disable_auto_exposure(self) -> None:
        self.CAP_PROP_EXPOSURE = 0.25
        
    def enable_auto_exposure(self) -> None:
        self.CAP_PROP_EXPOSURE = 0.75
        
    def edit_settings(self) -> None:
        """ 
        Launch the platform-controlled webcam settings.
        This is only available with the cv2.CAP_DSHOW backend.
        """
        self.CAP_PROP_SETTINGS = 0
        
    def get_info(self, name: str) -> dict:
        info = {"name": name}
        
        
        return info


if __name__ == "__main__":
    
    def test():
        from PIL import Image 
        
        with UsbCamera() as cam:
            while True:
                try:
                    
                    for prop in cam._cap_props:
                        print(prop, (getattr(cam, prop)))
                        
                    break
                    
                    array = cam.get_array()
                    Image.fromarray(array).show()
                    break
                    
                except KeyboardInterrupt:
                    break
        
    test()
        
