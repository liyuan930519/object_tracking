import math
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class DetectionResult:
    visible: bool
    x: float
    y: float


class RedObjectDetector:
    def __init__(
        self,
        min_area: float = 300.0,
    ) -> None:
        self.min_area = 0.0
        self.set_min_area(min_area)

    def set_min_area(
        self,
        min_area: float,
    ) -> None:
        if min_area <= 0:
            raise ValueError("min_area must be positive.")

        self.min_area = float(min_area)

    def detect(
        self,
        image: np.ndarray,
    ) -> DetectionResult:
        if image is None or image.size == 0:
            raise ValueError("Input image is empty.")

        if image.ndim != 3 or image.shape[2] != 3:
            raise ValueError("Expected a BGR image with 3 channels.")

        hsv = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2HSV,
        )

        lower_red_1 = np.array(
            [0, 120, 70],
            dtype=np.uint8,
        )
        upper_red_1 = np.array(
            [10, 255, 255],
            dtype=np.uint8,
        )

        lower_red_2 = np.array(
            [170, 120, 70],
            dtype=np.uint8,
        )
        upper_red_2 = np.array(
            [180, 255, 255],
            dtype=np.uint8,
        )

        mask_1 = cv2.inRange(
            hsv,
            lower_red_1,
            upper_red_1,
        )

        mask_2 = cv2.inRange(
            hsv,
            lower_red_2,
            upper_red_2,
        )

        mask = cv2.bitwise_or(
            mask_1,
            mask_2,
        )

        kernel = np.ones(
            (5, 5),
            dtype=np.uint8,
        )

        mask = cv2.morphologyEx(
            mask,
            cv2.MORPH_OPEN,
            kernel,
        )

        mask = cv2.morphologyEx(
            mask,
            cv2.MORPH_CLOSE,
            kernel,
        )

        contours, _ = cv2.findContours(
            mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )

        if not contours:
            return DetectionResult(
                visible=False,
                x=math.nan,
                y=math.nan,
            )

        contour = max(
            contours,
            key=cv2.contourArea,
        )

        area = cv2.contourArea(contour)

        if area < self.min_area:
            return DetectionResult(
                visible=False,
                x=math.nan,
                y=math.nan,
            )

        moments = cv2.moments(contour)

        if moments["m00"] == 0:
            return DetectionResult(
                visible=False,
                x=math.nan,
                y=math.nan,
            )

        x = moments["m10"] / moments["m00"]

        y = moments["m01"] / moments["m00"]

        return DetectionResult(
            visible=True,
            x=float(x),
            y=float(y),
        )
