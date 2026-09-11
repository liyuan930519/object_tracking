import cv2
import numpy as np
import pytest
from tracker_pkg.detector import RedObjectDetector


def test_detects_red_object():
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.circle(image, (320, 240), 40, (0, 0, 255), -1)
    detector = RedObjectDetector(min_area=100.0)
    result = detector.detect(image)
    assert result.visible is True
    assert result.x == pytest.approx(320.0, abs=2.0)
    assert result.y == pytest.approx(240.0, abs=2.0)


def test_no_object_returns_not_visible():
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    detector = RedObjectDetector(min_area=100.0)
    result = detector.detect(image)
    assert result.visible is False
    assert np.isnan(result.x)
    assert np.isnan(result.y)


def test_object_below_min_area_is_not_visible():
    image = np.zeros((200, 200, 3), dtype=np.uint8)
    cv2.circle(image, (100, 100), 5, (0, 0, 255), -1)
    detector = RedObjectDetector(min_area=500.0)
    result = detector.detect(image)
    assert result.visible is False
    assert np.isnan(result.x)
    assert np.isnan(result.y)


def test_empty_image_raises_value_error():
    detector = RedObjectDetector()
    image = np.array([], dtype=np.uint8)
    with pytest.raises(ValueError, match="Input image is empty"):
        detector.detect(image)


def test_invalid_image_shape_raises_value_error():
    detector = RedObjectDetector()
    image = np.zeros((480, 640), dtype=np.uint8)
    with pytest.raises(ValueError, match="Expected a BGR image"):
        detector.detect(image)


def test_invalid_min_area_raises_value_error():
    with pytest.raises(ValueError, match="min_area must be positive"):
        RedObjectDetector(min_area=0.0)


def test_selects_largest_red_object():
    image = np.zeros((400, 600, 3), dtype=np.uint8)
    cv2.circle(image, (100, 200), 20, (0, 0, 255), -1)
    cv2.circle(image, (450, 200), 50, (0, 0, 255), -1)
    detector = RedObjectDetector(min_area=100.0)
    result = detector.detect(image)
    assert result.visible is True
    assert result.x == pytest.approx(450.0, abs=2.0)
    assert result.y == pytest.approx(200.0, abs=2.0)
