# -*- coding: utf-8 -*-
"""
Assorted image processing operations.
"""

import numpy as np
import cmapy


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
