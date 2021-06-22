## About ##
FRHEED is a GUI for real-time Reflection High-Energy Electron Diffraction (RHEED) analysis.


## Installation ##
To install the latest release from PyPI:

`pip install frheed`

To install directly from GitHub for the latest unreleased development build:

`pip install git+https://github.com/ecyoung3/FRHEED.git`

If using a FLIR camera, the Spinnaker SDK must also be downloaded from the [FLIR website](https://www.flir.com/products/spinnaker-sdk/).
Click "Download Now" and find the appropriate version under Windows > Latest Spinnaker SDK. 
Note that this is liable to change, but is accurate as of June 21, 2021.
For more details on the Spinnaker SDK, view the [README](https://github.com/ecyoung3/FRHEED/blob/dev/frheed/cameras/flir/spinnaker_win32/README.txt).


## Hardware ##
FRHEED has been tested with the following cameras:
* Generic USB (Logitech brand)
* FLIR Blackfly S Mono 3.2MP GigE


## Usage ##
To start the main GUI:
```python
from frheed.gui import show
show()
```

## More Information ##
FRHEED was developed in October 2018 as a replacement to existing commercial RHEED software in Chris Palmstrom's research group at the University of California, Santa Barbara. It was initially installed on a single Molecular Beam Epitaxy (MBE) system in the Palmstrom Lab, but was quickly installed on other systems both within the Palmstrom group as well as other research groups at UCSB. Since then, FRHEED gone through multiple major overhauls and refactors and is now used by several research groups worldwide.

I welcome any feedback and suggestions for new features as I continue to work on improving FRHEED to be the most viable replacement to commercial software that it can be.
