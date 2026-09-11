import math

import rclpy
from cv_bridge import CvBridge, CvBridgeError
from objtrk_interfaces.msg import ObjectState
from rcl_interfaces.msg import SetParametersResult
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image

from tracker_pkg.detector import RedObjectDetector


class TrackerNode(Node):
    def __init__(self) -> None:
        super().__init__("tracker_node")

        self.declare_parameter(
            "min_area",
            300.0,
        )

        min_area = self.get_parameter("min_area").value

        self._detector = RedObjectDetector(
            min_area=min_area,
        )

        self.add_on_set_parameters_callback(self._on_parameters_changed)

        self._bridge = CvBridge()

        self._publisher = self.create_publisher(
            ObjectState,
            "tracker/object_state",
            10,
        )

        self._subscription = self.create_subscription(
            Image,
            "camera/image_raw",
            self._image_callback,
            qos_profile_sensor_data,
        )

        self.get_logger().info("Tracker node started.")

    def _on_parameters_changed(
        self,
        parameters,
    ) -> SetParametersResult:
        """Validate and apply runtime-safe tracker parameters."""
        new_min_area = None

        for parameter in parameters:
            if parameter.name == "min_area":
                try:
                    new_min_area = float(parameter.value)
                except (TypeError, ValueError):
                    return SetParametersResult(
                        successful=False,
                        reason="min_area must be a number.",
                    )

                if new_min_area <= 0:
                    return SetParametersResult(
                        successful=False,
                        reason="min_area must be positive.",
                    )

        if new_min_area is not None:
            self._detector.set_min_area(new_min_area)
            self.get_logger().info(f"Updated min_area to {new_min_area}.")

        return SetParametersResult(
            successful=True,
        )

    def _image_callback(
        self,
        message: Image,
    ) -> None:
        state = ObjectState()

        state.header = message.header

        try:
            frame = self._bridge.imgmsg_to_cv2(
                message,
                desired_encoding="bgr8",
            )

            result = self._detector.detect(frame)

            state.visible = result.visible
            state.x = result.x
            state.y = result.y

        except (
            CvBridgeError,
            ValueError,
        ) as error:
            self.get_logger().error(f"Image processing failed: {error}")

            state.visible = False
            state.x = math.nan
            state.y = math.nan

        self._publisher.publish(state)


def main(args=None) -> int:
    rclpy.init(args=args)

    node = TrackerNode()

    try:
        rclpy.spin(node)

    except (
        KeyboardInterrupt,
        ExternalShutdownException,
    ):
        pass

    finally:
        node.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
