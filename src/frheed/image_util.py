"""Image processing utilities."""

import cv2
import numpy as np
import numpy.typing as npt
from PyQt6 import QtGui

ImageArray = npt.NDArray[np.generic]


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
    return np.copy(image[y1:y2, x1:x2])


def get_ellipse_region(image: ImageArray, x1: int, y1: int, x2: int, y2: int) -> ImageArray:
    """Returns the region of an image bound by an ellipse."""
    # Get the region within the ellipse bounding box
    region = get_rectangle_region(image, x1, y1, x2, y2)

    # Create an elliptical mask where 1 = pixel to include, 0 = pixel to exclude
    height, width = region.shape[:2]
    center_x = width // 2
    center_y = height // 2
    mask = np.zeros((height, width), dtype=np.uint8)
    cv2.ellipse(
        mask,
        center=(center_x, center_y),
        axes=(center_x, center_y),
        angle=0,
        startAngle=0,
        endAngle=360,
        color=(1,),
        thickness=-1,  # negative thickness will draw a filled ellipse
    )

    # Set all pixels outside the elliptical mask to 0
    return cv2.bitwise_and(region, region, mask=mask)


def get_line_region(
    image: ImageArray, x1: int, y1: int, x2: int, y2: int, thickness: int = 1
) -> ImageArray:
    """Returns the region of an image under a line."""
    # Get the region within the line bounding box
    region = get_rectangle_region(image, x1, y1, x2, y2)

    # Create a mask by drawing the line
    height, width = region.shape[:2]
    mask = np.zeros((height, width), dtype=np.uint8)
    cv2.line(region, pt1=(0, 0), pt2=(height, width), color=(1,), thickness=thickness)

    # Set all pixels not under the line to 0
    return cv2.bitwise_and(region, region, mask=mask)
