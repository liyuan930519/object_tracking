#!/usr/bin/env python3
import argparse
import math
import sys
import time

import rclpy
from objtrk_interfaces.msg import ObjectState
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image


class SmokeObserver(Node):
    def __init__(self) -> None:
        super().__init__("smoke_observer")
        self.image_count = 0
        self.state_count = 0
        self.last_image_width = None
        self.last_image_height = None
        self.last_image_frame_id = None
        self.last_state_frame_id = None
        self.image_contract_ok = False
        self.valid_visible_state_seen = False
        self.last_state_reason = "No tracking state received yet."

        self.create_subscription(
            Image,
            "/camera/image_raw",
            self._on_image,
            qos_profile_sensor_data,
        )
        self.create_subscription(
            ObjectState,
            "/tracker/object_state",
            self._on_state,
            10,
        )

    def _on_image(self, msg: Image) -> None:
        self.image_count += 1
        self.last_image_width = msg.width
        self.last_image_height = msg.height
        self.last_image_frame_id = msg.header.frame_id
        self.image_contract_ok = (
            msg.width > 0
            and msg.height > 0
            and msg.encoding == "bgr8"
            and bool(msg.header.frame_id)
        )

    def _on_state(self, msg: ObjectState) -> None:
        self.state_count += 1
        self.last_state_frame_id = msg.header.frame_id

        if not msg.visible:
            self.last_state_reason = "Latest ObjectState reports visible=false."
            return
        if not math.isfinite(msg.x) or not math.isfinite(msg.y):
            self.last_state_reason = "Visible target has non-finite coordinates."
            return
        if self.last_image_width is None or self.last_image_height is None:
            self.last_state_reason = (
                "Tracking state arrived before an image was observed."
            )
            return
        if not (0.0 <= msg.x < self.last_image_width):
            self.last_state_reason = (
                f"x={msg.x} is outside image width {self.last_image_width}."
            )
            return
        if not (0.0 <= msg.y < self.last_image_height):
            self.last_state_reason = (
                f"y={msg.y} is outside image height {self.last_image_height}."
            )
            return
        if not msg.header.frame_id:
            self.last_state_reason = "ObjectState.header.frame_id is empty."
            return
        if self.last_image_frame_id and msg.header.frame_id != self.last_image_frame_id:
            self.last_state_reason = (
                "ObjectState frame_id does not match the observed image frame_id."
            )
            return

        self.valid_visible_state_seen = True
        self.last_state_reason = "Valid visible target observed."

    def observed_node_names(self) -> set[str]:
        return set(self.get_node_names())

    def application_nodes_present(self) -> bool:
        names = self.observed_node_names()
        return "camera_node" in names and "tracker_node" in names

    def passed(self) -> bool:
        return (
            self.application_nodes_present()
            and self.image_count >= 3
            and self.image_contract_ok
            and self.state_count >= 1
            and self.valid_visible_state_seen
        )

    def diagnostic_summary(self) -> str:
        names = self.observed_node_names()
        return (
            f"camera_node_present={'camera_node' in names}, "
            f"tracker_node_present={'tracker_node' in names}, "
            f"images={self.image_count}, "
            f"states={self.state_count}, "
            f"image_contract_ok={self.image_contract_ok}, "
            f"last_image={self.last_image_width}x{self.last_image_height}, "
            f"image_frame_id={self.last_image_frame_id!r}, "
            f"state_frame_id={self.last_state_frame_id!r}, "
            f"valid_visible_state_seen={self.valid_visible_state_seen}, "
            f"state_detail={self.last_state_reason}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Observe an already-running ROS 2 object-tracking deployment."
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Maximum seconds to wait for smoke-test criteria.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.timeout <= 0:
        print("ERROR: --timeout must be > 0.", file=sys.stderr)
        return 2

    rclpy.init()
    observer = SmokeObserver()
    deadline = time.monotonic() + args.timeout

    try:
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(observer, timeout_sec=0.1)
            if observer.passed():
                print("SMOKE TEST PASS")
                print(observer.diagnostic_summary())
                return 0

        print("SMOKE TEST FAIL", file=sys.stderr)
        print(observer.diagnostic_summary(), file=sys.stderr)
        return 1
    finally:
        observer.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
