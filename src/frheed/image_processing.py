"""
Assorted image processing operations.
"""

import cv2
import numpy as np
from matplotlib import pyplot as plt
from PyQt6.QtGui import QImage, QPixmap


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


def apply_cmap(arr: np.ndarray, cmap_name: str, bgr_order: bool = False) -> np.ndarray:
    """
    Apply a named colormap to an array.

    Parameters
    ----------
    arr : np.ndarray
        The array to apply the colormap to. The array must be single-channel (not RGB).
    cmap : str
        The name of the colormap to apply (any valid matplotlib colormap).
    rgbA_order : bool
        Whether the provided array is in BGR order instead of RGB order.

    Returns
    -------
    np.ndarray
        The original array with the colormap applied to it.
        The resulting array will be RGB888 (RGB where each channel is uint8).
        It will have a shape of (h, w, 3) where (h, w) are the height
        and width of the input array.

    """
    cmap = plt.get_cmap(cmap_name, 256)
    rgba_data = plt.cm.ScalarMappable(cmap=cmap).to_rgba(np.arange(0, 1, 1 / 256), bytes=True)
    rgba_data = rgba_data[:, 0:-1].reshape((256, 1, 3))

    # Convert to 3-channel RGB/BGR uint8 for OpenCV
    cmap_data = np.zeros((256, 1, 3), np.uint8)

    # Remove the alpha channel and optionally reverse RGB to BGR
    if bgr_order:
        cmap_data[:, :, :] = rgba_data[:, :, ::-1]
    else:
        cmap_data[:, :, :] = rgba_data[:, :, :]

    return cv2.applyColorMap(arr, cmap_data)


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
    """Convert a grayscale image to a QImage."""
    # Copy the array otherwise you could get an error that QImage argument 1
    # has unexpected type 'memoryview'
    array = array.copy()

    # Convert to QImage
    h, w = array.shape[0:2]
    bytes_per_line = array.strides[0]  # assuminng C-contiguous array
    return QImage(array.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)


def ndarray_to_qpixmap(array: np.ndarray) -> QPixmap:
    """Convert a numpy array to a QPixmap."""
    return QPixmap(ndarray_to_qimage(array))


def column_to_image(column: np.ndarray | list) -> np.ndarray:
    # Convert column to ndarray
    column = np.array(column)

    # Convert to 2D array
    return column[::-1, np.newaxis]


def extend_image(image: np.ndarray, new_col: np.ndarray) -> np.ndarray:
    """Append a new column onto the right side of an image."""
    # Make sure the new column is the same height as the image
    # If it isn't, pad the edges with np.nan
    h, w = image.shape[:2]
    if new_col.size != h:
        print(f"Image height {h} does not match column height {new_col.size}")
        return column_to_image(new_col)

    return np.append(image, column_to_image(new_col), axis=1)


def get_valid_colormaps() -> list[str]:
    return list(plt.colormaps())
