# FRHEED
A program for real-time Reflection High Energy Electron Diffraction (RHEED) analysis.

## Getting Started

Make sure that you have installed pip and Python 3.6 or higher. I recommend using Anaconda with the Spyder IDE.  

Download the following files from the main branch and move them to a folder of your choice:
* FRHEED.py
* FRHEED.ui
* FRHEED icon.ico
* All colormap .png files
* config.ini

### Prerequisites

The following packages are required in addition to the default Python 3.6 libraries. The lines of codes can be copy/pasted into the appropriate command window to install the package. Use the second line ('conda install...') if working with Anaconda.

```
cv2		
    python -m pip install opencv-python  (General installation)
    conda install -c conda-forge opencv  (Anaconda installation)

numpy		
      python -m pip install numpy
      conda install -c anaconda numpy

colormap	
    python -m pip install colormap
    conda install -c conda-forge colormap

matplotlib	
    python -m pip install matplotlib
    conda install -c conda-forge matplotlib

PIL		
    python -m pip install Pillow
    conda install -c anaconda pillow

PyQt5		
    pip install PyQt5
    conda install -c anaaconda pyqt

pyqtgraph	
    python -m pip install pyqtgraph
    conda install -c anaconda pyqtgraph

scipy		
    python -m pip install scipy
    conda install -c anaconda scipy

PySpin		
    Available from the FLIR website at the following links (you may need to create a FLIR account):
	Windows 10 (32-bit): https://www.ptgrey.com/support/downloads/11107/
	Windows 10 (64-bit): https://www.ptgrey.com/support/downloads/11106/
	
	Unzip the cp36 folder and open a command prompt there, then execute the command:
	    python -m pip install numpy spinnaker_python-1.15.0.63-cp36-cp36m-win_amd64.whl
```

## Running FRHEED

Once all required files are downloaded and located in the same folder and the required packages are installed, run FRHEED.py using Spyder (or your IDE of choice). If all went according to plan, it should run properly and will prompt you to select your default save location and which type of camera your computer is using.

However, things more than likely did NOT go according to plan, so it's up to you to troubleshoot. (sorry!)

## Features and Functions

* Upon initial startup, the user will be prompted to select a base save location and camera type
* The save directory will automatically be set to ~\Grower\Sample Name where ~ is the base save location (e.g. C:\Users\Desktop\FRHEED)
* The grower and sample name can be changed using the "Change Grower" and "Change Sample" buttons, respectively
* The "Open Directory" button will open a File Explorer window at the directory where files are currently being saved to
* The "Capture Image" button will capture an image of the current camera frame with the annotation on the bottom of the frame
* Press the "Record Video" button to begin recording video, and press it again to stop
* All saved images and videos will automatically be named according to the sample name and timestamp when saved
* The "Show Shapes" button will display 3 rectangles (red, green, and blue) on the camera frame. They are set to the max. camera frame size by default, so you may need to resize them before you can see them
  * Change which rectangle is being edited using the "Editing Red" button, or by clicking the mouse scroll wheel on the camera frame
  * Re-draw a rectangle by clicking and dragging with the left mouse button
  * Edit a rectangle without redrawing it by right-clicking and dragging on one of its sides
* The "Move Shapes" button doesn't do anything for now
* The "Start Live Plot" button will begin plotting the pixel intensity vs. time of the selected rectangular regions
  * The plot will show the summed pixel intensity by default, but this can be changed to the average intensity from within the code
  * Clicking "Stop Live Plot" will pause collection and display the most recently collected data in the "Newer" tab
  * Stopping and starting collection again will move the "Newer" data to the "Older" plot and update the "Newer" plot with the most recently collected data
* The "Update FFT" button will perform an FFT on each of the curves in the Live Data plot and display the position of the maximum peak
  * If you wish to manually calculate peak spacing:
    * Update the number of usable peaks in the intensity data using the "Number of peaks" spinbox
    * Click the left mouse button once at the first (chronologically) peak position
    * Click the left mouse button again at the final peak position
    * The average peak spacing will be displayed in the upper left-hand corner of the plot
* Basic notes can be collected and saved in the "Growth Notes" tab below the camera frame
* The image can be modified (exposure, background subtraction, and inversion) in the "Image" tab
  * The "Set High Exposure" and "Set Low Exposure" will instantly adjust the camera exposure to user-selected exposure values; these values will be saved to config.ini and automatically loaded in if the program is restarted
  * If a FLIR Gigabit Ethernet camera is being used, the exact exposure time (in milliseconds) can be set
* Colormaps can be applied to the image in the "Colormap" tab; the colormaps will also be applied to saved images and videos
  * The "Hot" colormap actually applies the "Seismic" colormap
* The "Timer" tab contains a timer and stopwatch, which perform as you would expect

## Planned Additions

* Lattice strain tracking by 1D intensity profiling
* Advanced camera settings, such as gamma and white balance
* 3D plotting for the camera frame
* Zooming in or out on the camera frame without resizing the window
* Further image annotation customization
* Ability to automatically stop/start recording video when the RHEED shutter is opened/closed
* Expand the colormap library and automatically plot a sample without having to explicitly import images

## Known Bugs

* Spyder will require a kernel restart every time after running the program
* The 'Annotation' frame flickers when resizing the main window
* The program slows down considerably if the camera frame is scaled to larger than its native resolution
	* This primarily affects webcams with low (640x480) native resolution
	* Not really a "bug" since upscaling the image requires a cubic interpolation calculation, which takes time

## Author

### Elliot Young ###  
University of California, Santa Barbara  
[Chris Palmstrøm Research Group](https://palmstrom.cnsi.ucsb.edu/)  
ecyoung@ucsb.edu

## License

This project is licensed under the GNU General Public License. Please see [LICENSE](https://github.com/ecyoung3/FRHEED/blob/master/LICENSE) for details.

## Acknowledgments

* kSA and Riber for making RHEED software expensive enough to warrant the creation of FRHEED
