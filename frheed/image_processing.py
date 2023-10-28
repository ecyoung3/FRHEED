# -*- coding: utf-8 -*-
"""
Assorted image processing operations.
"""

from typing import Union, List

import numpy as np
import cmapy
import cv2
import matplotlib as mpl
from PyQt5.QtGui import QImage, QPixmap

# https://stackoverflow.com/a/1735122/10342097
def normalize(arr: np.ndarray) -> np.ndarray:
    """
    Normalize a numpy array between 0 and 255 as uint8.
    
    Parameters
    ----------
    arr : np.ndarray
        The array to normalize.
    
    %timeit results (1536 x 2048, float32):
        6.41 ms ± 248 µs per loop (mean ± std. dev. of 7 runs, 100 loops each)
        
    """
    
    # Return if array is already uint8
    dtype = arr.dtype
    if dtype == np.uint8:
        return arr
    
    # Cast to floating point if it isn't already
    # https://stackoverflow.com/a/1168729/10342097
    if dtype.kind in ("u", "i"):
        
        # Warning: copy=False means the original input is modified!
        arr = arr.astype(np.float32, copy=True)
        
    # Normalize between 0 and 255
    arr *= 255 / arr.max()
    
    # Convert back to uint8
    return arr.astype(np.uint8, copy=True)
    
def apply_cmap(arr: np.ndarray, cmap: str) -> np.ndarray:
    """
    Apply a named colormap to an array. This function uses the cmapy library 
    to convert matplotlib colormaps to cv2 colormaps, since cv2.applyColormap is
    approximately 5x faster than using matplotlib/numpy methods 
    (tested using uint8 2048 x 1536 arrays, ~30ms vs ~6ms).

    Parameters
    ----------
    arr : np.ndarray
        The array to apply the colormap to. The array must be single-channel (not RGB).
    cmap : str
        The name of the colormap to apply (any valid matplotlib colormap).

    Returns
    -------
    np.ndarray
        The original array with the colormap applied to it.
        The resulting array will be RGB888 (RGB where each channel is uint8).
        It will have a shape of (h, w, 3) where (h, w) are the height
        and width of the input array.

    """
    return cmapy.colorize(normalize(arr), cmap, rgb_order=True)

def to_grayscale(array: np.ndarray) -> np.ndarray:
    # Get number of channels
    shape = array.shape
    channels = 1 if len(shape) == 2 else shape[-1]
    
    # Convert to grayscale if image is 3-channel
    if channels == 3:
        return cv2.cvtColor(array, cv2.COLOR_BGR2GRAY)
    
    # Convert to grayscale if RGBA
    elif channels == 4:
        return cv2.cvtColor(array, cv2.COLOR_RGBA2GRAY)
    
    # Otherwise, assume already grayscale
    return array

def ndarray_to_qimage(array: np.ndarray) -> QImage:
    """ Convert a grayscale image to a QImage. """
    # Copy the array otherwise you could get an error that QImage argument 1
    # has unexpected type 'memoryview'
    array = array.copy()
    
    # Convert to QImage
    h, w = array.shape[0:2]
    bytes_per_line = array.strides[0]  # assuminng C-contiguous array
    return QImage(array.data, w, h, bytes_per_line, QImage.Format_RGB888)

def ndarray_to_qpixmap(array: np.ndarray) -> QPixmap:
    """ Convert a numpy array to a QPixmap. """
    return QPixmap(ndarray_to_qimage(array))

def column_to_image(column: Union[np.ndarray, list]) -> np.ndarray:
    # Convert column to ndarray
    column = np.array(column)
    
    # Convert to 2D array
    return column[::-1, np.newaxis]

def extend_image(img: np.ndarray, new_col: np.ndarray, pad: bool=True) -> np.ndarray:
    """ Append a new column onto the right side of an image. """
    # Convert new column to 2D array so it can be appended to image
    col = column_to_image(new_col)
    
    # Get image and column dimensions
    im_h, im_w = img.shape[:2]
    col_h, col_w = new_col.size, 1
    
    # If column and image are same height, append column to image
    if im_h == col_h:
        return np.append(img, col, axis=1)
    
    # If padding and column is taller than image, pad image w/ zeros
    elif pad and col_h > im_h:
        # Create "blank" image
        new_img = np.zeros((col_h, im_w))
        
        # Paste the old image vertically centered
        dy = int((col_h - im_h) / 2)
        new_img[dy:dy+im_h, :] = img
        
        return np.append(new_img, col, axis=1)
        
    # If padding and column is shorter than image, pad column w/ zeros
    elif pad and col_h < im_h:
        # Create "blank" column
        _col = np.zeros((im_h, 1))
        
        # Paste the column vertically centered
        dy = int((im_h - col_h) / 2)
        _col[dy:dy+col_h, :] = col
        
        return np.append(img, _col, axis=1)
        
    # If not padding and sizes don't match, create a new image
    elif not pad and col_h != im_h:
        return col
    
def get_valid_colormaps() -> List[str]:
    return mpl.pyplot.colormaps()


if __name__ == "__main__":
    
    import time
    
    from FRHEED.utils import sample_array
    
    class NormTests:
        def norm_0(arr: np.ndarray) -> np.ndarray:
            # 7.04 ms ± 235 µs per loop (mean ± std. dev. of 7 runs, 100 loops each)
            arr = arr.astype(np.float32, copy=False)
            arr *= 255 / arr.max()
            return arr.astype(np.uint8, copy=False)
        
        def norm_1(arr: np.ndarray) -> np.ndarray:
            # 12.3 ms ± 170 µs per loop (mean ± std. dev. of 7 runs, 100 loops each)
            return (arr * (255 / arr.max())).astype(np.uint8, copy=False)
            
        def norm_2(arr: np.ndarray) -> np.ndarray:
            # 12.3 ms ± 394 µs per loop (mean ± std. dev. of 7 runs, 100 loops each)
            info = np.iinfo(arr.dtype)
            arr = 255 * (arr.astype(np.float32, copy=False) / info.max)
            arr = arr.astype(np.uint8, copy=False)
            return arr
    
    c = 1
    # arr_uint8 = sample_array(channels=c, dtype="uint8")
    # arr_uint16 = sample_array(channels=c, dtype="uint16")
    arr_float32 = sample_array(channels=c, dtype="float32")
    
    t0 = time.time()
    normed = normalize(arr_float32)
    print(f"Normalized array in {time.time()-t0:.5f} seconds")
    
    t0 = time.time()
    cmap = "Spectral"
    mapped = apply_cmap(normed, cmap)
    print(f"Applied colormap in {time.time()-t0:.5f} seconds")
    
    print(get_valid_colormaps())
