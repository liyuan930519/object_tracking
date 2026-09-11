import numpy as np
import pytest
from camera_pkg.fake_camera import FakeCameraSource


def test_fake_camera_returns_image():
    camera = FakeCameraSource(width=320, height=240, radius=20)
    assert camera.open() is True
    success, frame = camera.read()
    assert success is True
    assert frame is not None
    assert frame.shape == (240, 320, 3)
    assert frame.dtype == np.uint8
    red_pixels = (frame[:, :, 2] > 200) & (frame[:, :, 1] < 50) & (frame[:, :, 0] < 50)
    assert np.any(red_pixels)
    camera.close()


def test_closed_fake_camera_cannot_read():
    camera = FakeCameraSource(width=320, height=240, radius=20)
    success, frame = camera.read()
    assert success is False
    assert frame is None


def test_fake_camera_rejects_invalid_dimensions():
    with pytest.raises(ValueError):
        FakeCameraSource(width=50, height=50, radius=20)
