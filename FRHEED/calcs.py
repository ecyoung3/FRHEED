# -*- coding: utf-8 -*-
"""
Functions for computing values from plots.
"""

import math

import numpy as np

from FRHEED.utils import snip_lists


def calc_fft(x: list, y: list) -> tuple:
    # Make sure data is equal lengths
    # Note: this is probably unnecessary if pulling 
    # data directly from another plot
    x, y = snip_lists(x, y)
    
    # Return if x or y is invalid
    def invalid_data(data):
        return len(data) == 0 or np.nan in data
    if any(invalid_data(d) for d in (x, y)):
        return None, None
    
    # Create evenly-spaced list of sample points 
    numsamples = len(x)
    samplespacing = (x[-1]-x[0])/numsamples
    
    # Generate array of frequencies
    try:
        freq = np.fft.rfftfreq(numsamples, d=samplespacing)
    except:
        return None, None
    
    # Remove DC signal from the y-data
    y -= np.mean(y)
    
    # Apply Hanning filter to smooth edge discontinuities
    window = np.hanning(numsamples+1)[:-1]
    if len(y) != len(window):
        return None, None
    hann = y*window

    # Calculate real FFT
    fftdata = np.fft.rfft(hann)
    
    # Normalize FFT data
    try:
        psd = abs(fftdata)**2/(np.abs(hann)**2).sum()
        psd = (psd*2)**0.5
    except RuntimeWarning:
        return None, None
    
    # Sometimes the arrays can become different lengths and throw errors
    freq, psd = snip_lists(freq, psd)
    
    return (freq, psd)

def find_peaks(xvals: list, yvals: list) -> tuple:
    pass # TODO


if __name__ == "__main__":
    pass
