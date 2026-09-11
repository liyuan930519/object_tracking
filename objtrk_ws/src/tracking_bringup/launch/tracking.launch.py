from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    default_config_file = PathJoinSubstitution(
        [
            FindPackageShare("tracking_bringup"),
            "config",
            "tracking.yaml",
        ]
    )

    config_file = LaunchConfiguration("config_file")

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "config_file",
                default_value=default_config_file,
                description=("Path to the ROS 2 YAML parameter file."),
            ),
            Node(
                package="camera_pkg",
                executable="camera_node",
                name="camera_node",
                output="screen",
                parameters=[
                    config_file,
                ],
            ),
            Node(
                package="tracker_pkg",
                executable="tracker_node",
                name="tracker_node",
                output="screen",
                parameters=[
                    config_file,
                ],
            ),
        ]
    )
