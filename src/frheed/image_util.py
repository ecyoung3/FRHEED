"""Image processing utilities."""

import cv2
import numpy as np
import numpy.typing as npt
from PyQt6 import QtGui

ImageArray = npt.NDArray[np.generic]


def get_image_shape(image: ImageArray) -> tuple[int, int, int]:
    """Returns the height, width, and number of channels of an image.

    Raises:
        TypeError if the image has less than 2 dimensions or greater than 3 dimensions.
    """
    match image.ndim:
        case 2:
            height, width = image.shape
            channels = 1
        case 3:
            height, width, channels = image.shape
        case _:
            raise TypeError(f"Image with shape {image.shape} has unsupported number of dimensions")

    return (height, width, channels)


def qimage_to_ndarray(image: QtGui.QImage) -> ImageArray:
    """Converts a QImage to a numpy array."""
    if (image_bits := image.bits()) is None:
        raise ValueError("Image contains no data")

    width = image.width()
    height = image.height()
    depth = image.depth() // 8  # bits to bytes

    image_bytes = image_bits.asstring(image.sizeInBytes())
    image_array = np.frombuffer(image_bytes, dtype=np.uint8).reshape((height, width, depth))
    return image_array


def get_rectangle_region(image: ImageArray, x1: int, y1: int, x2: int, y2: int) -> ImageArray:
    """Returns the region of an image bound by a rectangle."""
    # The region must have nonzero dimensions
    h, w = image.shape[:2]
    return np.copy(image[min(y1, h - 2) : max(y2, y1 + 1), min(x1, w - 2) : max(x2, x1 + 1)])


def get_ellipse_region(image: ImageArray, x1: int, y1: int, x2: int, y2: int) -> ImageArray:
    """Returns the region of an image bound by an ellipse."""
    # Get the region within the ellipse bounding box
    region = get_rectangle_region(image, x1, y1, x2, y2)

    # Mask all pixels outside the ellipse
    height, width, channels = get_image_shape(region)
    center_x = width // 2
    center_y = height // 2
    mask = np.ones(region.shape, dtype=np.uint8)
    cv2.ellipse(
        mask,
        center=(center_x, center_y),
        axes=(center_x, center_y),
        angle=0,
        startAngle=0,
        endAngle=360,
        color=[0] * channels,
        thickness=-1,  # negative thickness will draw a filled ellipse
    )
    return np.ma.MaskedArray(region, mask=np.ma.make_mask(mask))


def get_line_region(
    image: ImageArray, x1: int, y1: int, x2: int, y2: int, thickness: int = 1
) -> ImageArray:
    """Returns the region of an image under a line."""
    # Get the region within the line bounding box
    region = get_rectangle_region(image, x1, y1, x2, y2)
    if x1 == x2 or y1 == y2:
        # Region is already a line and does not require masking
        return region

    # Mask all pixels not under the line
    height, width, channels = get_image_shape(region)
    mask = np.zeros(region.shape, dtype=np.uint8)
    cv2.line(mask, pt1=(0, 0), pt2=(height, width), color=[0] * channels, thickness=thickness)
    return np.ma.MaskedArray(region, mask=np.ma.make_mask(mask))
