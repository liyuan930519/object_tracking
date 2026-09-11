import cv2
import numpy as np

from camera_pkg.camera_source import CameraSource


class FakeCameraSource(CameraSource):
    def __init__(
        self,
        width: int,
        height: int,
        radius: int = 40,
    ) -> None:
        if width <= 2 * radius + 20:
            raise ValueError("Camera width is too small for the fake object.")

        if height <= 2 * radius:
            raise ValueError("Camera height is too small for the fake object.")

        self.width = width
        self.height = height
        self.radius = radius

        self._opened = False
        self._frame_index = 0

    def open(self) -> bool:
        self._opened = True
        return True

    def read(self) -> tuple[bool, np.ndarray | None]:
        if not self._opened:
            return False, None

        frame = np.zeros(
            (self.height, self.width, 3),
            dtype=np.uint8,
        )

        margin = self.radius + 10
        movement_width = self.width - 2 * margin

        x = margin + (self._frame_index * 8) % movement_width
        y = self.height // 2

        cv2.circle(
            frame,
            (x, y),
            self.radius,
            (0, 0, 255),
            -1,
        )

        self._frame_index += 1

        return True, frame

    def close(self) -> None:
        self._opened = False
