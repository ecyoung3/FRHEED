# -*- coding: utf-8 -*-

"""
Install the spinnaker .whl file located in /spinnaker/...
"""

import os
from pathlib import Path
import re

from frheed.utils import install_whl, get_logger


logger = get_logger()


def install_pyspin() -> None:
    """ Install PySpin from the appropriate .whl file """
    
    # Check if PySpin is already installed
    try:
        import PySpin
        if __name__ == "__main__":
            logger.info("PySpin is already installed")
        return 
    
    except ImportError:
        pass
    
    from frheed.utils import get_platform_bitsize
    
    # Determine bitsize of platform (32- and 64-bit Windows is supported currently)
    bitsize = get_platform_bitsize()
    
    if bitsize not in [32, 64]:
        msg = f"Unsupported platform bitsize: {bitsize}"
        logger.exception(msg)
        raise ValueError(msg)
        
    # Get proper .whl file
    whl_filepaths = []
    for root, dirs, files in os.walk(os.path.dirname(__file__)):
        for file in files:
            if re.search(fr"{bitsize}.*\.whl$", file):
                whl_filepaths.append(os.path.join(root, file))
        
    if not whl_filepaths:
        msg = f"Unable to find any .whl files for platform bitsize {bitsize}"
        logger.exception(msg)
        raise ValueError(msg)
        
    pretty_filepaths = "\n\t".join(whl_filepaths)
    logger.info(f"Found .whl files:\n{pretty_filepaths}")
    
    # Try to install each of the .whl files via subprocess
    # NOTE: Different .whl files are for different versions; try each one
    # https://stackoverflow.com/a/50255019/10342097
    for file in whl_filepaths:
        logger.info(f"Trying to install PySpin from {file}")
        exit_code = install_whl(file)
        whl_filepath = file
        if exit_code == 0:
            break

    # Verify that PySpin has been installed
    try:
        import PySpin
        logger.info(f"PySpin installed successfully from {whl_filepath}")
        
    except ImportError:
        logger.info(f"PySpin failed to install from {whl_filepath}")

if __name__ == "__main__":
    def test():
        os.chdir(str(Path(__file__).parents[3]))
        install_pyspin()
        
    test()
