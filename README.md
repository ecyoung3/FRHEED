# About
FRHEED is a GUI for real-time Reflection High-Energy Electron Diffraction (RHEED) analysis.

## Installation

To install the latest release from PyPI:

`pip install frheed`

To install directly from GitHub for the latest unreleased development build:

`pip install git+https://github.com/ecyoung3/FRHEED.git`

### PySpin

If using FRHEED with a FLIR camera, `PySpin` is also required.

To install[^1] `PySpin`:

  1. Download and install the latest [full Spinnaker SDK][spinnaker-sdk] for your platform.
  
  2. Download the latest [Python Spinnaker SDK][spinnaker-sdk] for your platform.

  3. Install the `.whl` file contained in the downloaded Python Spinnaker SDK:

  ```
  python -m pip install <path_to_whl_file>
  ```

For more installation details, see the `README.txt` contained within the downloaded Python Spinnaker SDK.

[^1]: These instructions are liable to change, but are accurate as of October 2023.

## Hardware

FRHEED has been tested with the following cameras:
* Generic USB (Logitech brand)
* FLIR Blackfly S Mono 3.2MP GigE


## Usage

To start the main GUI:
```python
from frheed.gui import show
show()
```

## More Information

FRHEED was developed in October 2018 as a replacement to existing commercial RHEED software in Chris Palmstrom's research group at the University of California, Santa Barbara. It was initially installed on a single Molecular Beam Epitaxy (MBE) system in the Palmstrom Lab, but was quickly installed on other systems both within the Palmstrom group as well as other research groups at UCSB. Since then, FRHEED gone through multiple major overhauls and refactors and is now used by several research groups worldwide.

The time I am able to devote towards developing FRHEED is much more limited these days, but I still welcome any feedback and new feature requests.


[spinnaker-sdk]: https://www.flir.com/support-center/iis/machine-vision/downloads/spinnaker-sdk-download
