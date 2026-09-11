from abc import ABC, abstractmethod

import numpy as np


class CameraSource(ABC):
    @abstractmethod
    def open(self) -> bool:
        """Open the camera source."""

    @abstractmethod
    def read(self) -> tuple[bool, np.ndarray | None]:
        """Read a single frame."""

    @abstractmethod
    def close(self) -> None:
        """Release camera resources."""
