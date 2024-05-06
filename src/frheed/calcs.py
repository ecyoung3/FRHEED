"""
Functions for computing values from plots.
"""

import warnings
from typing import TYPE_CHECKING

import numpy as np
from scipy.signal import find_peaks

from frheed.utils import snip_lists

if TYPE_CHECKING:
    from numpy.typing import NDArray

# Ignore numpy warnings
np.seterr("ignore")


def calc_fft(
    x: NDArray[np.float64], y: NDArray[np.float64]
) -> tuple[NDArray[np.float64], NDArray[np.float64]] | tuple[None, None]:
    """Calculate the FFT of a 1D series.

    Parameters
    ----------
    x : list
        X values.
    y : list
        Y values.

    Returns
    -------
    tuple
        A tuple containing (frequency, PSD) lists. PSD is Power Spectral Density.

    """
    # Make sure data is equal lengths
    # Note: this is probably unnecessary if pulling
    # data directly from another plot
    x, y, *_ = snip_lists(x, y)

    # Return if x or y is invalid
    def invalid_data(data: NDArray[np.float64]) -> bool:
        return len(data) == 0 or np.nan in data

    if any(invalid_data(d) for d in (x, y)):
        return None, None

    # Create evenly-spaced list of sample points
    numsamples = len(x)
    samplespacing = (x[-1] - x[0]) / numsamples

    # Generate array of frequencies
    freq = np.fft.rfftfreq(numsamples, d=samplespacing)

    # Convert y to float32 to avoid type conflict error in following operation
    y_arr = np.array(y, dtype=np.float32)

    # Remove DC signal from the y-data
    y_arr -= np.mean(y)

    # Apply Hanning filter to smooth edge discontinuities
    window = np.hanning(numsamples + 1)[:-1]
    if len(y_arr) != len(window):
        return None, None
    hann = y_arr * window

    # Calculate real FFT
    fftdata = np.fft.rfft(hann)

    # Normalize FFT data & catch warnings (RuntimeError) as exceptions
    with warnings.catch_warnings():
        warnings.filterwarnings("error")
        try:
            psd: np.ndarray = abs(fftdata) ** 2 / (np.abs(hann) ** 2).sum()
            psd = (psd * 2) ** 0.5
        except Warning:
            return None, None

    # Sometimes the arrays can become different lengths and throw errors
    freq, psd, *_ = snip_lists(freq, psd)

    return (freq, psd)


def apply_cutoffs(
    x: NDArray[np.float64],
    y: NDArray[np.float64],
    minval: float | None = None,
    maxval: float | None = None,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Return data that falls between a certain range. Pass None to use min or max of the array.

    Args:
        x (list): x values; data is filtered based on these values
        y (list): y values
        minval (Optional[float], optional): Cutoff minimum (inclusive).
        maxval (Optional[float], optional): Cutoff maximum (inclusive).

    Returns:
        tuple: the filtered x and y arrays
    """
    if (len(x) + len(y) == 0) or (minval is None and maxval is None):
        return (x, y)

    if minval is not None and maxval is None:
        # Create mask if there's a minimum cutoff but not maximum
        mask = x >= minval
    elif maxval is not None and minval is None:
        # Create mask if there's a maximum cutoff but not minimum
        mask = x <= maxval
    elif minval is not None and maxval is not None:
        # Mask both
        mask = (x >= minval) & (x <= maxval)

    # Return masked elements
    return (x[mask], y[mask])


def detect_peaks(
    x: NDArray[np.float64],
    y: NDArray[np.float64],
    min_freq: float | None = 0.0,
) -> list[float] | None:
    with warnings.catch_warnings():
        warnings.filterwarnings("error")

        try:
            # Filter to minimum frequency
            x, y = apply_cutoffs(x=x, y=y, minval=min_freq)

            # Height
            height = max(np.median(y) + 3 * np.std(y), 1.5)

            # Threshold (vertical distance to neighbors)
            threshold = None

            # Distance between peaks (# of indices)
            distance = 50

            # Prominence
            prominence = None

            # Find peaks
            peak_indices, _ = find_peaks(
                y, height=height, threshold=threshold, distance=distance, prominence=prominence
            )

            # Get corresponding x-coordinates
            return [x[idx] for idx in peak_indices]
        except Warning:
            return None


if __name__ == "__main__":
    pass
