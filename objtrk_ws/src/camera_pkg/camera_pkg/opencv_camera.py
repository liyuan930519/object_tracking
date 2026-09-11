import cv2
import numpy as np

from camera_pkg.camera_source import CameraSource


class OpenCVCameraSource(CameraSource):
    def __init__(
        self,
        device_path: str,
        width: int,
        height: int,
        fps: float,
    ) -> None:
        self.device_path = device_path
        self.width = width
        self.height = height
        self.fps = fps

        self._capture: cv2.VideoCapture | None = None

    def open(self) -> bool:
        try:
            self._capture = cv2.VideoCapture(self.device_path)

            if not self._capture.isOpened():
                self.close()
                return False

            self._capture.set(
                cv2.CAP_PROP_FRAME_WIDTH,
                self.width,
            )
            self._capture.set(
                cv2.CAP_PROP_FRAME_HEIGHT,
                self.height,
            )
            self._capture.set(
                cv2.CAP_PROP_FPS,
                self.fps,
            )

            return True
        except cv2.error:
            self.close()
            return False

    def read(self) -> tuple[bool, np.ndarray | None]:
        if self._capture is None:
            return False, None

        try:
            success, frame = self._capture.read()
        except cv2.error:
            return False, None

        if not success:
            return False, None

        return True, frame

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None
