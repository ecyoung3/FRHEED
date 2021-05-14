# -*- coding: utf-8 -*-

"""
Install the spinnaker .whl file located in /spinnaker/...
"""

import os
from pathlib import Path
import re
import subprocess
import sys

def install_pyspin() -> None:
    """ Install PySpin from the appropriate .whl file """
    
    # Check if PySpin is already installed
    try:
        import PySpin
        if __name__ == "__main__":
            print("PySpin is already installed")
        return 
    
    except ImportError:
        pass
    
    from FRHEED.utils import get_platform_bitsize
    
    # Determine bitsize of platform (32- and 64-bit Windows is supported currently)
    bitsize = get_platform_bitsize()
    
    if bitsize not in [32, 64]:
        raise ValueError(f"Unsupported platform bitsize: {bitsize}")
        
    # Get proper .whl file
    whl_filepath = None
    for root, dirs, files in os.walk(os.path.dirname(__file__)):
        for file in files:
            if re.search(fr"{bitsize}.*\.whl$", file):
                whl_filepath = os.path.join(root, file)
        
    if whl_filepath is None:
        raise ValueError(f"Unable to find .whl file for bitsize {bitsize}")
    
    # Try to install the .whl file via subprocess
    # https://stackoverflow.com/a/50255019/10342097
    print(subprocess.check_call([sys.executable, "-m", "pip", "install", whl_filepath]))

    # Verify that PySpin has been installed
    try:
        import PySpin
        print(f"PySpin installed successfully from {whl_filepath}")
        
    except ImportError:
        print(f"PySpin failed to install from {whl_filepath}")

if __name__ == "__main__":
    def test():
        os.chdir(str(Path(__file__).parents[3]))
        install_pyspin()
        
    test()
