"""
Connecting to FLIR cameras.
Adapted from simple_pyspin: https://github.com/klecknerlab/simple_pyspin
"""

import time
from collections import deque
from typing import Tuple, Union

import numpy as np

from frheed.cameras import CameraError

# Make sure PySpin is installed
from frheed.cameras.flir.install_pyspin import install_pyspin

install_pyspin()
import PySpin

# Editable camera settings to show
_GUI_SETTINGS = {
    "AcquisitionFrameRate": "Frame Rate",
    "AcquisitionFrameRateEnable": "Enable Frame Rate",
    "BinningHorizontal": "Horizontal Binning",
    "BinningHorizontalMode": "Horizontal Binning Mode",
    "BinningVertical": "Vertical Binning",
    "BinningVerticalMode": "Vertical Binning Mode",
    "BlackLevel": "Black Level",
    "DeviceIndicatorMode": "LED Behaviour",
    "DeviceUserID": "Camera Name",
    "ExposureAuto": "Auto-Exposure",
    "ExposureMode": "Exposure Mode",
    "ExposureTime": "Exposure Time",  # microseconds
    "GainAuto": "Auto-Gain",
    "Gain": "Gain",  # note: read-only if GainAuto is True
    "Gamma": "Gamma",
    "GammaEnable": "Enable Gamma",
}

# Read-only camera information to show
_GUI_INFO = {
    "Width": "Frame Width",
    "SensorWidth": "Sensor Width",
    "WidthMax": "Maximum Frame Width",  # calculated after horizontal binning
    "Height": "Frame Height",
    "SensorHeight": "Sensor Height",
    "HeightMax": "Maximum Frame Height",  # calculated after vertical binning
    "DeviceVendorName": "Vendor",
    "DeviceModelName": "Model",
    "DeviceID": "Serial Number",
    "DeviceTLType": "Type",  # e.g. GigEVision
    "DeviceTemperature": "Temperature",
    "DeviceUptime": "Uptime",
    "DeviceVersion": "Firmware Version",
    "PixelDynamicRangeMin": "Dynamic Range Minimum",  # e.g. 0
    "PixelDynamicRangeMax": "Dynamic Range Maximum",  # e.g. 256
    "PixelFormat": "Pixel Format",
    "PixelSize": "Pixel Size",  # bits per pixel,
    "PowerSupplyCurrent": "Current",
    "PowerSupplyVoltage": "Voltage",
    "SerialPortBaudRate": "Baud Rate",
}

# Camera functions to show
_GUI_FUNCTIONS = {
    "DeviceReset": "Reboot",
    "FactoryReset": "Factory Reset",
    "SerialReceiveQueueClear": "Clear Serial Port",
}

_DEBUG = __name__ == "__main__"

_SYSTEM = None


def list_cameras() -> PySpin.CameraList:
    """
    Return a list of Spinnaker cameras. Also initializes the PySpin
    'System', if needed. (See PySpin documentation for more info.)
    """

    global _SYSTEM

    if _SYSTEM is None:
        _SYSTEM = PySpin.System.GetInstance()

    return _SYSTEM.GetCameras()


def get_available_cameras() -> dict:
    """Get available cameras as a dictionary of {source: name}."""
    cams = list_cameras()
    num_cams = cams.GetSize()
    available = {}

    for src in range(num_cams):
        try:
            with FlirCamera(src=src) as cam:
                if cam.initialized:
                    available[src] = str(cam)
                else:
                    print(f"FLIR camera {src} is not available")
        except CameraError:
            print("No FLIR cameras detected")

    return available


class FlirCamera:
    """
    A class used to encapsulate a PySpin camera.
    Attributes
    ----------
    cam : PySpin Camera
    running : bool
        True if acquiring images
    camera_attributes : dictionary
        Contains links to all of the camera nodes which are settable
        attributes.
    camera_methods : dictionary
        Contains links to all of the camera nodes which are executable
        functions.
    camera_node_types : dictionary
        Contains the type (as a string) of each camera node.
    lock : bool
        If True, attribute access is locked down; after the camera is
        initialized, attempts to set new attributes will raise an error.  This
        is to prevent setting misspelled attributes, which would otherwise
        silently fail to acheive their intended goal.
    intialized : bool
        If True, init() has been called.

    In addition, many more virtual attributes are created to allow access to
    the camera properties.  A list of available names can be found as the keys
    of 'camera_attributes' dictionary, and a documentation file for a specific
    camera can be genereated with the 'document' method.

    Methods
    -------
    init()
        Initializes the camera.  Automatically called if the camera is opened
        using a 'with' clause.
    close()
        Closes the camera and cleans up.  Automatically called if the camera
        is opening using a 'with' clause.
    start()
        Start recording images.
    stop()
        Stop recording images.
    get_image()
        Return an image using PySpin"s internal format.
    get_array()
        Return an image as a Numpy array.
    get_info(node)
        Return info about a camera node (an attribute or method).
    document()
        Create a Markdown documentation file with info about all camera
        attributes and methods.

    """

    _rw_modes = {
        PySpin.RO: "read only",
        PySpin.RW: "read/write",
        PySpin.WO: "write only",
        PySpin.NA: "not available",
    }

    _attr_types = {
        PySpin.intfIFloat: PySpin.CFloatPtr,
        PySpin.intfIBoolean: PySpin.CBooleanPtr,
        PySpin.intfIInteger: PySpin.CIntegerPtr,
        PySpin.intfIEnumeration: PySpin.CEnumerationPtr,
        PySpin.intfIString: PySpin.CStringPtr,
    }

    _attr_type_names = {
        PySpin.intfIFloat: "float",
        PySpin.intfIBoolean: "bool",
        PySpin.intfIInteger: "int",
        PySpin.intfIEnumeration: "enum",
        PySpin.intfIString: "string",
        PySpin.intfICommand: "command",
    }

    def __init__(self, src: Union[int, str] = 0, lock: bool = False):
        """
        Parameters
        ----------
        src : int or str (default: 0)
            If an int, the index of the camera to acquire.  If a string,
            the serial number of the camera.
        lock : bool (default: False)
            If True, setting new attributes after initialization results in
            an error.
        """
        super().__setattr__("camera_attributes", {})
        super().__setattr__("camera_methods", {})
        super().__setattr__("camera_node_types", {})
        super().__setattr__("_initialized", False)
        super().__setattr__("lock", lock)

        cam_list = list_cameras()

        if _DEBUG:
            print(f"Found {cam_list.GetSize()} FLIR camera(s)")

        self._src_type = type(src)
        self._src = src

        if not cam_list.GetSize():
            raise CameraError("No FLIR cameras detected.")

        if isinstance(src, int):
            self._cam = cam_list.GetByIndex(src)

        elif isinstance(src, str):
            self._cam = cam_list.GetBySerial(src)

        cam_list.Clear()

        # Other attributes which may be accessed later
        self._running = False
        self._frame_times = deque()
        self._incomplete_image_count = 0

    def __getattr__(self, attr: str) -> object:
        # Add this in so @property decorator works as expected
        if attr in self.__dict__:
            return self.__dict__[attr]

        elif attr in self.camera_attributes:
            prop = self.camera_attributes[attr]
            if not PySpin.IsReadable(prop):
                raise CameraError(f"Camera property '{attr}' is not readable")

            if hasattr(prop, "GetValue"):
                return prop.GetValue()
            elif hasattr(prop, "ToString"):
                return prop.ToString()
            else:
                raise CameraError(f"Camera property '{attr}' is not readable")

        elif attr in self.camera_methods:
            return self.camera_methods[attr].Execute

        else:
            raise AttributeError(attr)

    def __setattr__(self, attr: str, val: object) -> None:
        if attr in self.camera_attributes:
            prop = self.camera_attributes[attr]
            if not PySpin.IsWritable(prop):
                raise CameraError(f"Property '{attr}' is not currently writable!")

            if hasattr(prop, "SetValue"):
                prop.SetValue(val)
            else:
                prop.FromString(val)

        elif attr in self.camera_methods:
            raise CameraError(
                f"Camera method '{attr}' is a function -- " "you can't assign it a value!"
            )
        else:
            if attr == "__class__":
                super().__setattr__(attr, val)
            elif attr not in self.__dict__ and self.lock and self.initialized:
                raise CameraError(f"Unknown property '{attr}'.")
            else:
                super().__setattr__(attr, val)

    def __enter__(self) -> "FlirCamera":
        self.init()
        return self

    def __exit__(self, type, value, traceback) -> None:
        self.close()

    def __del__(self) -> None:
        # Close the camera
        try:
            self.close()

        # If "with" clause is called and camera doesn't exist, AttributeError will happen
        except AttributeError:
            pass

    def __str__(self) -> str:
        model = getattr(self, "DeviceModelName", "Camera")
        return f"FLIR {model} (SN {self.DeviceSerialNumber})"

    @property
    def name(self) -> str:
        return f"FLIR{self._src}"

    @property
    def camera_type(self) -> str:
        return "FLIR"

    @property
    def cam(self) -> PySpin.PySpin.CameraPtr:
        return self._cam

    @property
    def initialized(self) -> bool:
        return self._initialized

    @property
    def running(self) -> bool:
        return self._running

    @property
    def incomplete_image_count(self) -> int:
        return self._incomplete_image_count

    @property
    def model(self) -> str:
        """Camera model, including vendor and device model name"""
        return f"{self.DeviceVendorName.strip()} {self.DeviceModelName.strip()}"

    @property
    def settings(self) -> dict:
        """Get public, accessible camera settings as a dictionary"""
        settings = {}
        for attr in sorted(self.camera_attributes.keys()):
            # Skip private attributes
            if "_" in attr:
                continue

            # Get attribute information
            info = self.get_info(attr)

            # Skip inaccessible attributes
            if not info.get("access", 0):
                continue

            # Add attribute to settings
            settings[attr] = info

        return settings

    @property
    def gui_settings(self) -> dict:
        """User-editable attributes to show in a GUI"""
        return _GUI_SETTINGS

    @property
    def gui_info(self) -> dict:
        """Read-only attributes to show in a GUI"""
        return _GUI_INFO

    @property
    def gui_functions(self) -> dict:
        """User-accessible functions to show in a GUI"""
        return _GUI_FUNCTIONS

    @property
    def real_fps(self) -> float:
        """Get the real frames per second (Hz)"""

        # When not enough frames have been captured
        if len(self._frame_times) <= 1:
            return 0.0

        # Calculate average of all frames
        else:
            dt = self._frame_times[-1] - self._frame_times[0]
            return len(self._frame_times) / max(dt, 1)

    @property
    def width(self) -> int:
        if not self.initialized:
            self.init()
            width = self.Width
            self.close()

        else:
            width = self.Width

        return int(width)

    @property
    def height(self) -> int:
        if not self.initialized:
            self.init()
            height = self.Height
            self.close()

        else:
            height = self.Height

        return int(height)

    @property
    def shape(self) -> Tuple[int, int]:
        """Get the camera array dimensions (Height x Width)"""
        if not self.initialized:
            self.init()
            shape = (self.Height, self.Width)
            self.close()

        else:
            shape = (self.Height, self.Width)

        return shape

    def init(self) -> None:
        """
        Initializes the camera. Automatically called if the camera is opened
        using a 'with' clause.
        """

        self.cam.Init()

        for node in self.cam.GetNodeMap().GetNodes():
            pit = node.GetPrincipalInterfaceType()
            name = node.GetName()
            self.camera_node_types[name] = self._attr_type_names.get(pit, pit)
            if pit == PySpin.intfICommand:
                self.camera_methods[name] = PySpin.CCommandPtr(node)
            if pit in self._attr_types:
                self.camera_attributes[name] = self._attr_types[pit](node)

        self._initialized = True

    def start(self, continuous: bool = True) -> None:
        """
        Start capturing frames from the camera.

        Parameters
        ----------
        continuous : bool, optional
            Whether to capture frames continuously or one at a time. The default is True.

        Returns
        -------
        None
            DESCRIPTION.

        """

        # Set acquisition mode to "Continuous" (i.e. streaming)
        # This has to be done prior to initialization
        # TODO: Support other acquisition modes
        if continuous:
            self.AcquisitionMode = "Continuous"

        # Initialize the camera
        if not self.initialized:
            self.init()

        # Begin acquisition
        if not self.running:
            if not self.cam.IsStreaming():
                self.cam.BeginAcquisition()
            self._running = True

    def stop(self) -> None:
        """Stop recording images."""

        if self.running:
            self.cam.EndAcquisition()
        self._frame_times = deque()
        self._incomplete_image_count = 0
        self._running = False

    def close(self) -> None:
        """
        Closes the camera and cleans up. Automatically called if the camera
        is opening using a 'with' clause.
        """

        # Stop the camera
        self.stop()
        try:
            del self.cam
        except AttributeError:
            pass

        # Reset attributes
        self.camera_attributes = {}
        self.camera_methods = {}
        self.camera_node_types = {}
        self._initialized = False
        # self.system.ReleaseInstance()

    def get_image(self, wait: bool = True) -> PySpin.ImagePtr:
        """
        Get an image from the camera.
        Parameters
        ----------
        wait : bool (default: True)
            If True, waits for the next image.  Otherwise throws an exception
            if there isn"t one ready.
        Returns
        -------
        img : PySpin Image
        """

        # Make sure the camera is running
        if not self.running:
            self.start()

        # Get the image pointer
        image_ptr = self.cam.GetNextImage(
            PySpin.EVENT_TIMEOUT_INFINITE if wait else PySpin.EVENT_TIMEOUT_NONE
        )

        # Check if the image is incomplete
        if image_ptr.IsIncomplete():
            self._incomplete_image_count += 1

        # Release the image pointer to free memory (I think this reduces performance?)
        # image_ptr.Release()  # free memory in the camera buffer

        return image_ptr

    def get_array(
        self, wait: bool = True, get_chunk: bool = False, complete_frames_only: bool = False
    ) -> Union[np.ndarray, Tuple[np.ndarray, PySpin.PySpin.ChunkData]]:
        """
        Get an image from the camera, and convert it to a numpy array.

        Parameters
        ----------
        wait : bool (default: True)
            If True, waits for the next image.  Otherwise throws an exception
            if there isn"t one ready.
        get_chunk : bool (default: False)
            If True, returns chunk data from image frame.
        complete_frames_only : bool (default: True)
            If True, only return complete frames.

        Returns
        -------
        img : numpy.ndarray
        chunk : PySpin.PySpin.ChunkData (only if get_chunk == True)
        """

        # Get image pointer
        img = self.get_image(wait=wait)

        # Ensure complete image is returned if option is chosen
        if complete_frames_only and img.IsIncomplete():
            return self.get_array(wait, get_chunk, complete_frames_only)

        # Store frame time for real FPS calculation
        self._frame_times.append(time.time())

        # Remove the oldest frame if there are more than 60
        if len(self._frame_times) > 3600:
            self._frame_times.popleft()

        if get_chunk:
            return img.GetNDArray(), img.GetChunkData()
        else:
            return img.GetNDArray()

    def get_info(self, name: str) -> dict:
        """
        Get information on a camera node (attribute or method).

        Parameters
        ----------
        name : string
            The name of the desired node
        Returns
        -------
        info : dict
            A dictionary of retrieved properties.  *Possible* keys include:
                - "access": read/write access of node.
                - "description": description of node.
                - "value": the current value.
                - "unit": the unit of the value (as a string).
                - "min" and "max": the min/max value.
        """
        info = {"name": name}

        if name in self.camera_attributes:
            node = self.camera_attributes[name]
        elif name in self.camera_methods:
            node = self.camera_methods[name]
        else:
            raise ValueError(f"'{name}' is not a camera method or attribute")

        info["type"] = self.camera_node_types[name]

        if hasattr(node, "GetAccessMode"):
            access = node.GetAccessMode()
            info["access"] = self._rw_modes.get(access, access)
            if isinstance(info["access"], str) and "read" in info["access"]:
                info["value"] = getattr(self, name)

        if info.get("access") != 0:
            for attr in ("description", "unit", "min", "max"):
                fname = "Get" + attr.capitalize()
                f = getattr(node, fname, None)
                if f:
                    info[attr] = f()
            if hasattr(node, "GetEntries"):
                entries = []
                entry_desc = []
                has_desc = False
                for entry in node.GetEntries():
                    entries.append(entry.GetName().split("_")[-1])
                    entry_desc.append(entry.GetDescription().strip())
                    if entry_desc[-1]:
                        has_desc = True
                info["entries"] = entries
                if has_desc:
                    info["entry_descriptions"] = entry_desc

        return info

    def document(self, verbose: bool = True) -> str:
        """
        Creates a MarkDown documentation string for the camera.

        Parameters
        ----------
        verbose : bool, optional
            Whether to show documentation details, including default access,
            value, and range. The default is True.

        Returns
        -------
        str
            A string describing the camera attributes and methods.

        """

        # Get basic camera information, including model and version
        lines = [self.model]
        lines.append("=" * len(lines[-1]))
        lines.append("")
        lines.append("*Version: %s*" % getattr(self, "DeviceVersion", "?"))
        lines.append("")

        # Get camera attributes
        lines.append("Attributes")
        lines.append("-" * len(lines[-1]))
        lines.append("")

        for attr in sorted(self.camera_attributes.keys()):
            # Skip private attributes
            if "_" in attr:
                continue
            # print(attr)

            # Get attribute information
            info = self.get_info(attr)
            if not info.get("access", 0):
                continue
            lines.append(f"{attr}: {info.get('type', '?')}")

            # Skip details if not verbose (gives shorter markdown document)
            if not verbose:
                continue

            # Get attribute description
            lines.append("  " + info.get("description", "(no description provided)"))

            # Get default access
            lines.append("  - default access: %s" % info.get("access", "?"))
            if "value" in info:
                lines.append("  - default value: %s" % repr(info["value"]))
            if "unit" in info and info["unit"].strip():
                lines.append("  - unit: %s" % info["unit"])
            if "min" in info and "max" in info:
                lines.append("  - default range: %s - %s" % (info["min"], info["max"]))
            if "entries" in info:
                if "entry_descriptions" in info:
                    lines.append("  - possible values:")
                    for e, ed in zip(info["entries"], info["entry_descriptions"]):
                        if ed:
                            lines.append("    - '%s': %s" % (e, ed))
                        else:
                            lines.append("    - '%s'" % e)
                else:
                    lines.append(
                        "  - possible values: %s" % (", ".join("'%s'" % e for e in info["entries"]))
                    )

            lines.append("")

        # Get camera methods
        lines.append("")
        lines.append("Methods")
        lines.append("-" * len(lines[-1]))
        lines.append("")
        lines.append(
            (
                "**Note: the camera recording should be started/stopped"
                " using the 'start' and 'stop' methods, not any of the functions"
                " below (see simple_pyspin documentation).**"
            )
        )
        lines.append("")

        for attr in sorted(self.camera_methods.keys()):
            # Skip private methods
            if "_" in attr:
                continue
            # print(attr)

            # Get method information
            info = self.get_info(attr)
            lines.append("%s():  " % (attr))

            # Get method description
            lines.append("  " + info.get("description", "(no description provided)"))

            # Skip details if not verbose (gives shorter markdown document)
            if not verbose:
                lines.append("")
                continue

            # Get method default access
            lines.append("  - default access: %s" % info.get("access", "?"))
            lines.append("")

        return "\n".join(lines)


if __name__ == "__main__":

    def test():
        with FlirCamera() as cam:
            print(cam.document(verbose=False))
            print(cam)
            cam.start()
            while True:
                try:
                    global image
                    image = cam.get_array()
                    # print(cam.incomplete_image_count, cam.real_fps)
                    print(cam.DeviceTemperature)

                except KeyboardInterrupt:
                    break

    # test()

    print(list_cameras())
