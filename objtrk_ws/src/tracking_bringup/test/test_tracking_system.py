import math
import time

import rclpy
from camera_pkg.camera_node import CameraNode
from objtrk_interfaces.msg import ObjectState
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from tracker_pkg.tracker_node import TrackerNode


def spin_until(executor, condition, timeout_sec=3.0):
    """Spin until condition is true or the timeout expires."""
    deadline = time.monotonic() + timeout_sec

    while not condition() and time.monotonic() < deadline:
        executor.spin_once(timeout_sec=0.05)

    return condition()


def test_fake_camera_to_tracker_end_to_end():
    """Verify CameraNode -> Image topic -> TrackerNode -> ObjectState."""
    rclpy.init()

    camera_node = CameraNode()
    tracker_node = TrackerNode()
    observer_node = Node("tracking_system_test_node")
    executor = SingleThreadedExecutor()

    images = []
    states = []

    # Keep these subscription objects alive for the whole test.
    image_subscription = observer_node.create_subscription(
        Image,
        "camera/image_raw",
        images.append,
        qos_profile_sensor_data,
    )
    state_subscription = observer_node.create_subscription(
        ObjectState,
        "tracker/object_state",
        states.append,
        10,
    )

    executor.add_node(camera_node)
    executor.add_node(tracker_node)
    executor.add_node(observer_node)

    try:
        parameter_results = camera_node.set_parameters(
            [
                Parameter(
                    "camera_mode",
                    Parameter.Type.STRING,
                    "fake",
                ),
                Parameter(
                    "width",
                    Parameter.Type.INTEGER,
                    320,
                ),
                Parameter(
                    "height",
                    Parameter.Type.INTEGER,
                    240,
                ),
                Parameter(
                    "fps",
                    Parameter.Type.DOUBLE,
                    10.0,
                ),
            ]
        )

        assert all(result.successful for result in parameter_results)
        assert camera_node.start() is True

        # Make sure the observer has discovered both system publishers.
        connected = spin_until(
            executor,
            lambda: (
                image_subscription.get_publisher_count() > 0
                and state_subscription.get_publisher_count() > 0
            ),
        )
        assert connected, (
            "The system publishers were not discovered within the timeout."
        )

        received_pipeline_output = spin_until(
            executor,
            lambda: bool(images) and bool(states),
            timeout_sec=3.0,
        )
        assert received_pipeline_output, (
            "The camera/tracker pipeline did not produce output within the timeout."
        )

        image = images[-1]
        state = states[-1]

        # CameraNode output contract.
        assert image.width == 320
        assert image.height == 240
        assert image.encoding == "bgr8"

        # TrackerNode output contract.
        assert state.visible is True
        assert math.isfinite(state.x)
        assert math.isfinite(state.y)
        assert 0.0 <= state.x < image.width
        assert 0.0 <= state.y < image.height

        # TrackerNode copies the source image header into ObjectState.
        assert state.header.frame_id == image.header.frame_id
        assert state.header.frame_id != ""

    finally:
        camera_node.stop()

        executor.remove_node(camera_node)
        executor.remove_node(tracker_node)
        executor.remove_node(observer_node)

        camera_node.destroy_node()
        tracker_node.destroy_node()
        observer_node.destroy_node()
        executor.shutdown()

        if rclpy.ok():
            rclpy.shutdown()
