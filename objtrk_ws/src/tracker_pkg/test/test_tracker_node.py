import math
import time

import cv2
import numpy as np
import pytest
import rclpy
from cv_bridge import CvBridge
from objtrk_interfaces.msg import ObjectState
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from tracker_pkg.tracker_node import TrackerNode


def spin_until(executor, condition, timeout_sec=2.0):
    """Spin until condition is true or the timeout expires."""
    deadline = time.monotonic() + timeout_sec

    while not condition() and time.monotonic() < deadline:
        executor.spin_once(timeout_sec=0.05)

    return condition()


@pytest.fixture
def tracker_harness():
    """Create a TrackerNode and a small ROS test node."""
    rclpy.init()

    tracker_node = TrackerNode()
    test_node = Node("tracker_test_node")
    executor = SingleThreadedExecutor()

    received_states = []

    image_publisher = test_node.create_publisher(
        Image,
        "camera/image_raw",
        qos_profile_sensor_data,
    )

    state_subscription = test_node.create_subscription(
        ObjectState,
        "tracker/object_state",
        received_states.append,
        10,
    )

    executor.add_node(tracker_node)
    executor.add_node(test_node)

    try:
        connected = spin_until(
            executor,
            lambda: (
                image_publisher.get_subscription_count() > 0
                and state_subscription.get_publisher_count() > 0
            ),
        )

        assert connected, (
            "TrackerNode publishers/subscribers did not connect within the timeout."
        )

        yield {
            "tracker_node": tracker_node,
            "test_node": test_node,
            "executor": executor,
            "image_publisher": image_publisher,
            "received_states": received_states,
        }

    finally:
        executor.remove_node(tracker_node)
        executor.remove_node(test_node)

        tracker_node.destroy_node()
        test_node.destroy_node()
        executor.shutdown()

        if rclpy.ok():
            rclpy.shutdown()


def publish_image_and_wait_for_state(
    harness,
    image,
    frame_id="test_camera",
    timeout_sec=2.0,
):
    """Publish an OpenCV image through ROS and wait for ObjectState."""
    received_states = harness["received_states"]
    received_states.clear()

    bridge = CvBridge()
    message = bridge.cv2_to_imgmsg(
        image,
        encoding="bgr8",
    )
    message.header.frame_id = frame_id
    message.header.stamp = harness["test_node"].get_clock().now().to_msg()

    deadline = time.monotonic() + timeout_sec

    while not received_states and time.monotonic() < deadline:
        harness["image_publisher"].publish(message)
        harness["executor"].spin_once(timeout_sec=0.05)

    assert received_states, (
        "TrackerNode did not publish ObjectState within the timeout."
    )

    return received_states[-1]


def test_tracker_node_publishes_detection(tracker_harness):
    """A red image arriving over ROS should produce a visible state."""
    image = np.zeros(
        (480, 640, 3),
        dtype=np.uint8,
    )
    cv2.circle(
        image,
        (320, 240),
        40,
        (0, 0, 255),
        -1,
    )

    state = publish_image_and_wait_for_state(
        tracker_harness,
        image,
    )

    assert state.visible is True
    assert state.x == pytest.approx(320.0, abs=2.0)
    assert state.y == pytest.approx(240.0, abs=2.0)
    assert state.header.frame_id == "test_camera"


def test_tracker_node_reports_not_visible(tracker_harness):
    """No target should still produce a valid invisible ObjectState."""
    image = np.zeros(
        (480, 640, 3),
        dtype=np.uint8,
    )

    state = publish_image_and_wait_for_state(
        tracker_harness,
        image,
    )

    assert state.visible is False
    assert math.isnan(state.x)
    assert math.isnan(state.y)
    assert state.header.frame_id == "test_camera"
