from typing import ClassVar

import rclpy
from cv_bridge import CvBridge
from rcl_interfaces.msg import SetParametersResult
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image

from camera_pkg.camera_source import CameraSource
from camera_pkg.fake_camera import FakeCameraSource
from camera_pkg.opencv_camera import OpenCVCameraSource


class CameraNode(Node):
    STARTUP_ONLY_PARAMETERS: ClassVar[set[str]] = {
        "camera_mode",
        "device_path",
        "width",
        "height",
    }

    def __init__(self) -> None:
        super().__init__("camera_node")

        self.declare_parameter(
            "camera_mode",
            "real",
        )
        self.declare_parameter(
            "device_path",
            "/dev/video0",
        )
        self.declare_parameter(
            "width",
            640,
        )
        self.declare_parameter(
            "height",
            480,
        )
        self.declare_parameter(
            "fps",
            10.0,
        )
        self.declare_parameter(
            "frame_id",
            "camera",
        )

        self._publisher = self.create_publisher(
            Image,
            "camera/image_raw",
            qos_profile_sensor_data,
        )

        self._bridge = CvBridge()

        self._source: CameraSource | None = None
        self._timer = None
        self._running = False

        self.failed = False

        self.add_on_set_parameters_callback(self._on_parameters_changed)

    def _on_parameters_changed(
        self,
        parameters,
    ) -> SetParametersResult:
        """Validate parameter updates and apply safe runtime changes."""
        new_fps = None

        # Validate the complete request before applying any side effects.
        for parameter in parameters:
            if self._running and parameter.name in self.STARTUP_ONLY_PARAMETERS:
                return SetParametersResult(
                    successful=False,
                    reason=(
                        f"{parameter.name} cannot be changed while "
                        "the camera is running. Restart the node to "
                        "apply this parameter."
                    ),
                )

            if parameter.name == "fps":
                try:
                    new_fps = float(parameter.value)
                except (TypeError, ValueError):
                    return SetParametersResult(
                        successful=False,
                        reason="fps must be a number.",
                    )

                if new_fps <= 0:
                    return SetParametersResult(
                        successful=False,
                        reason="fps must be positive.",
                    )

            if parameter.name == "frame_id" and (
                not isinstance(parameter.value, str) or not parameter.value
            ):
                return SetParametersResult(
                    successful=False,
                    reason="frame_id must be a non-empty string.",
                )

        # fps controls the camera node's target publish/read rate. If the
        # camera is already running, replace the timer immediately.
        if new_fps is not None and self._running:
            self._replace_publish_timer(new_fps)
            self.get_logger().info(f"Updated camera target FPS to {new_fps}.")

        return SetParametersResult(
            successful=True,
        )

    def _replace_publish_timer(
        self,
        fps: float,
    ) -> None:
        if self._timer is not None:
            self.destroy_timer(self._timer)

        self._timer = self.create_timer(
            1.0 / fps,
            self._publish_frame,
        )

    def start(self) -> bool:
        if self._running:
            return True

        mode = self.get_parameter("camera_mode").value
        device_path = self.get_parameter("device_path").value
        width = self.get_parameter("width").value
        height = self.get_parameter("height").value
        fps = self.get_parameter("fps").value
        frame_id = self.get_parameter("frame_id").value

        if width <= 0 or height <= 0:
            self.get_logger().error("Camera width and height must be positive.")
            return False

        if fps <= 0:
            self.get_logger().error("Camera FPS must be positive.")
            return False

        if not isinstance(frame_id, str) or not frame_id:
            self.get_logger().error("Camera frame_id must be a non-empty string.")
            return False

        try:
            if mode == "fake":
                self._source = FakeCameraSource(
                    width=width,
                    height=height,
                )

            elif mode == "real":
                self._source = OpenCVCameraSource(
                    device_path=device_path,
                    width=width,
                    height=height,
                    fps=fps,
                )

            else:
                self.get_logger().error(f"Unsupported camera_mode: {mode}")
                return False

        except ValueError as error:
            self.get_logger().error(f"Invalid camera configuration: {error}")
            return False

        if not self._source.open():
            source_name = device_path if mode == "real" else "fake camera"
            self.get_logger().error(f"Failed to open camera source: {source_name}")
            self._source = None
            return False

        self._running = True
        self.failed = False
        self._replace_publish_timer(float(fps))

        self.get_logger().info(f"Camera started in '{mode}' mode at {fps} FPS.")

        return True

    def _publish_frame(self) -> None:
        if self._source is None:
            return

        success, frame = self._source.read()

        if not success or frame is None or frame.size == 0:
            self.get_logger().error("Camera frame read failed.")

            self.failed = True
            self._running = False

            if self._timer is not None:
                self._timer.cancel()

            self._source.close()

            if rclpy.ok():
                rclpy.shutdown()

            return

        message = self._bridge.cv2_to_imgmsg(
            frame,
            encoding="bgr8",
        )

        message.header.stamp = self.get_clock().now().to_msg()
        message.header.frame_id = self.get_parameter("frame_id").value

        self._publisher.publish(message)

    def stop(self) -> None:
        self._running = False

        if self._timer is not None:
            self.destroy_timer(self._timer)
            self._timer = None

        if self._source is not None:
            self._source.close()
            self._source = None


def main(args=None) -> int:
    rclpy.init(args=args)

    node = CameraNode()

    exit_code = 0

    try:
        if not node.start():
            exit_code = 1
        else:
            rclpy.spin(node)

    except (
        KeyboardInterrupt,
        ExternalShutdownException,
    ):
        pass

    finally:
        if node.failed:
            exit_code = 1

        node.stop()
        node.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
