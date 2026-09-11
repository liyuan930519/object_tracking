# ROS 2 Object Tracking

A containerized ROS 2 object-tracking system built with **ROS 2 Jazzy**, **Python**, and **OpenCV**.

The system publishes camera images from one node, detects the largest valid red object in another node, and publishes the target visibility and pixel coordinates. The default runtime uses a physical webcam; a deterministic fake camera is included for automated tests and Docker smoke testing.

## Architecture

```text
CameraNode
  └─ /camera/image_raw  (sensor_msgs/msg/Image)
          ↓
TrackerNode
  └─ /tracker/object_state  (objtrk_interfaces/msg/ObjectState)
```

Packages:

- `camera_pkg`: camera node, physical/fake camera sources
- `tracker_pkg`: tracker node and red-object detector
- `objtrk_interfaces`: custom `ObjectState` message
- `tracking_bringup`: launch, YAML configuration, system test

`ObjectState.msg`:

```text
std_msgs/Header header
bool visible
float32 x
float32 y
```

`x` and `y` are image pixel coordinates with `(0, 0)` at the top-left.

When no valid target is detected:

```text
visible = false
x = NaN
y = NaN
```

## Tracking Approach

`RedObjectDetector`:

1. converts BGR to HSV;
2. thresholds two red hue ranges;
3. combines the masks;
4. applies morphological opening/closing;
5. finds external contours;
6. selects the largest contour;
7. rejects contours smaller than `min_area`;
8. computes the centroid from image moments.

If several red regions exist, only the largest valid region is reported.

## Configuration

Production configuration:

```text
objtrk_ws/src/tracking_bringup/config/tracking.yaml
```

```yaml
camera_node:
  ros__parameters:
    camera_mode: real
    device_path: /dev/video0
    width: 640
    height: 480
    fps: 10.0
    frame_id: camera

tracker_node:
  ros__parameters:
    min_area: 300.0
```

Fake configuration:

```text
objtrk_ws/src/tracking_bringup/config/tracking_fake.yaml
```

uses the same image settings with:

```yaml
camera_mode: fake
```

| Parameter | Default | Runtime behavior |
|---|---:|---|
| `camera_mode` | `real` | startup-only while running |
| `device_path` | `/dev/video0` | startup-only while running |
| `width` | `640` | startup-only while running |
| `height` | `480` | startup-only while running |
| `fps` | `10.0` | dynamic |
| `frame_id` | `camera` | dynamic |
| `min_area` | `300.0` | dynamic |

Examples (run in a shell where the ROS system is visible; for the Docker smoke test, run these **inside the running container**):

```bash
ros2 param set /camera_node fps 5.0
ros2 param set /tracker_node min_area 500.0
```

## Command Execution Context

Unless explicitly stated otherwise:

- **Host / WSL shell** means the development machine, not the running application container.
- **Repository root** means the directory containing `docker-compose.yml`, for example:

```text
~/object_tracking
```

- **ROS workspace root** means:

```text
<repo-root>/objtrk_ws
```

- Commands beginning with `docker compose ...` are run on the **host / WSL shell from the repository root**.
- Commands such as `ros2 node list` used to inspect the running Docker system are run **inside the running container** after `docker compose ... exec tracking bash`.
- `pre-commit`, `pipx`, and Git commands are run on the **host / WSL shell**, not inside the application container.

## Docker Build

Prerequisites:

- Docker
- Docker Compose
- native Linux + V4L2 webcam for physical-camera operation

Run on the **host / WSL shell from the repository root**:

```bash
cd ~/object_tracking
docker compose build
```

The Dockerfile uses `ros:jazzy-ros-base`, installs dependencies with `rosdep`, and builds the workspace with `colcon`.

## Run With a Physical Camera

Default host device:

```text
/dev/video0
```

Run on a **native Linux host from the repository root**:

```bash
cd <repo-root>
docker compose up
```

The production Compose file maps the selected host camera to a stable container path:

```text
Host camera -> Container /dev/video0
```

If the host camera is `/dev/video2`, run from the **repository root on the native Linux host**:

```bash
CAMERA_DEVICE=/dev/video2 docker compose up
```

Identify available video devices on the **native Linux host** (directory does not matter):

```bash
ls -l /dev/video*
```

or:

```bash
v4l2-ctl --list-devices
```

The ROS node still uses:

```yaml
device_path: /dev/video0
```

because Compose performs the host-to-container mapping.

## Camera Failure Behavior

If the physical camera cannot be opened, a clear error is logged and the camera executable exits with a non-zero code.

If frame capture fails after startup, the source is closed, ROS shutdown is requested, and the executable exits as a failure.

Normal `Ctrl+C` shutdown is handled without intentionally printing a noisy traceback.

## Fake-Camera Docker Smoke Test

For environments without direct webcam access, run on the **host / WSL shell from the repository root**:

```bash
cd ~/object_tracking
docker compose -f docker-compose.fake.yml up
```

Keep that terminal running. In a **second host / WSL terminal**, also from the repository root:

```bash
cd ~/object_tracking
docker compose -f docker-compose.fake.yml exec tracking bash
```

The following `ros2 ...` inspection commands in this section are then run **inside that container shell**.

Verify nodes:

```bash
ros2 node list
```

Expected:

```text
/camera_node
/tracker_node
```

Verify topics:

```bash
ros2 topic list
```

Expected:

```text
/camera/image_raw
/tracker/object_state
```

Verify fake mode:

```bash
ros2 param get /camera_node camera_mode
```

Expected:

```text
String value is: fake
```

Verify image rate:

```bash
ros2 topic hz /camera/image_raw
```

Expected: approximately **10 Hz**.

Verify tracking output:

```bash
ros2 topic echo /tracker/object_state
```

`FakeCameraSource` generates a moving red circle, so the tracker should normally report:

```text
visible: true
x: <finite pixel coordinate>
y: <finite pixel coordinate>
```

This smoke test validates:

```text
FakeCameraSource
    ↓
CameraNode
    ↓
/camera/image_raw
    ↓
TrackerNode
    ↓
/tracker/object_state
```

This Docker fake-camera runtime smoke test was executed successfully during development.

## Automated Tests

Automated tests do **not** require a physical camera.

The repository contains **13 `test_*` cases** across unit, ROS integration, and end-to-end system levels.

### Fake camera unit tests

File:

```text
objtrk_ws/src/camera_pkg/test/test_fake_camera.py
```

| Test function | Design purpose |
|---|---|
| `test_fake_camera_returns_image()` | Normal source path: verifies the fake camera opens and returns a valid BGR frame containing a red target. |
| `test_closed_fake_camera_cannot_read()` | Lifecycle/error path: verifies a closed source returns `(False, None)`. |
| `test_fake_camera_rejects_invalid_dimensions()` | Configuration validation: invalid dimensions must raise `ValueError`. |

### Detector unit tests

File:

```text
objtrk_ws/src/tracker_pkg/test/test_detector.py
```

| Test function | Design purpose |
|---|---|
| `test_detects_red_object()` | Normal tracking case: a known red circle must be detected near its expected centroid. |
| `test_no_object_returns_not_visible()` | No-object behavior: black image -> `visible=False`, `x/y=NaN`. |
| `test_object_below_min_area_is_not_visible()` | Threshold behavior: small red regions below `min_area` must be ignored. |
| `test_empty_image_raises_value_error()` | Invalid input: an empty image must be rejected explicitly. |
| `test_invalid_image_shape_raises_value_error()` | Invalid format: non-BGR image shape must be rejected. |
| `test_invalid_min_area_raises_value_error()` | Invalid configuration: non-positive `min_area` must be rejected. |
| `test_selects_largest_red_object()` | Multiple candidates: verifies the largest valid red region is selected. |

### Tracker ROS integration tests

File:

```text
objtrk_ws/src/tracker_pkg/test/test_tracker_node.py
```

These tests publish controlled `sensor_msgs/Image` messages through ROS and observe `ObjectState`.

| Test function | Design purpose |
|---|---|
| `test_tracker_node_publishes_detection(tracker_harness)` | Normal ROS pub/sub path: verifies visible target, expected centroid, and propagated `frame_id`. |
| `test_tracker_node_reports_not_visible(tracker_harness)` | ROS-level no-object path: verifies a valid invisible result with `NaN` coordinates is still published. |

Helpers such as `spin_until(...)`, `tracker_harness()`, and `publish_image_and_wait_for_state(...)` support the integration tests but are not standalone tests.

### End-to-end ROS system test

File:

```text
objtrk_ws/src/tracking_bringup/test/test_tracking_system.py
```

Test:

```python
def test_fake_camera_to_tracker_end_to_end():
```

Purpose: verify the complete ROS pipeline without manually injecting an image into the tracker.

```text
FakeCameraSource
    ↓
CameraNode
    ↓
/camera/image_raw
    ↓
TrackerNode
    ↓
/tracker/object_state
```

It verifies that:

- fake-camera parameters are accepted;
- `CameraNode.start()` succeeds;
- image and tracking publishers are discovered;
- an image and tracking state are produced;
- image dimensions/encoding are correct;
- the fake red target is detected;
- coordinates are finite and within image bounds;
- the image `frame_id` is propagated to `ObjectState.header`.

### Test summary

| Level | File | Count |
|---|---|---:|
| Camera-source unit | `test_fake_camera.py` | 3 |
| Detector unit | `test_detector.py` | 7 |
| Tracker ROS integration | `test_tracker_node.py` | 2 |
| End-to-end ROS system | `test_tracking_system.py` | 1 |
| **Total** |  | **13** |

## Run Tests

Run these commands on the **host / WSL Ubuntu shell**.

Start from the repository root, then enter the ROS workspace:

```bash
cd ~/object_tracking
source /opt/ros/jazzy/setup.bash
cd objtrk_ws

colcon build --symlink-install
source install/setup.bash

colcon test --event-handlers console_direct+
colcon test-result --verbose
```

After `cd objtrk_ws`, the build, source, and test commands are executed from the **ROS workspace root**.

## Pre-commit

`pre-commit` is a development tool and is installed on the **host / WSL Ubuntu environment**, not inside the application container.

Install `pipx` and `pre-commit` on the host:

```bash
sudo apt update
sudo apt install -y pipx
pipx ensurepath
pipx install pre-commit
```

If `pipx ensurepath` updates the shell PATH, open a new terminal (or reload the shell profile) before continuing.

From the **repository root**:

```bash
cd ~/object_tracking
pre-commit install
pre-commit run --all-files
```

`pre-commit install` installs the Git hook into this repository's `.git/hooks/` directory.

Configured checks include repository hygiene, YAML/XML validation, Ruff linting, and Ruff formatting.

If a hook modifies files automatically, review the changes and run:

```bash
pre-commit run --all-files
```

again from the repository root until all hooks pass.

## Known Limitations

### Physical webcam path under WSL2

Development and container smoke testing were performed under **WSL2**.

Direct physical webcam `/dev/video*` access was not available in that environment, so this exact hardware path was not directly validated:

```text
physical host webcam
    ↓
host /dev/video*
    ↓
Docker device passthrough
    ↓
container /dev/video0
    ↓
OpenCVCameraSource
```

The production Compose configuration follows the standard native-Linux V4L2 device-mapping model.

The complete containerized **software** pipeline was validated with `FakeCameraSource`.

Physical-camera passthrough should therefore be verified on a native Linux host with V4L2 camera access.

### Tracking limitations

- fixed HSV thresholds are sensitive to lighting and camera color response;
- unrelated red objects can cause false positives;
- only the largest valid red region is selected;
- no persistent track ID or temporal motion model is used;
- occlusion and multi-object tracking are not handled;
- no confidence score is published.

## Possible Extensions

Possible extensions include:

- configurable HSV thresholds;
- multiple cameras and namespaces;
- multi-object tracking with persistent IDs;
- Kalman filtering or optical flow;
- learned object detection;
- debug-image publication;
- ROS diagnostics and performance metrics;
- CI and automated container runtime tests.

## Quick Reference

All Docker Compose and pre-commit commands below are run on the **host / WSL shell from the repository root** unless noted otherwise.

Repository root:

```bash
cd ~/object_tracking
```

Build:

```bash
docker compose build
```

Run with the default physical camera on native Linux:

```bash
docker compose up
```

Run with another host camera:

```bash
CAMERA_DEVICE=/dev/video2 docker compose up
```

Run the fake-camera smoke test:

```bash
docker compose -f docker-compose.fake.yml up
```

Enter the running fake-camera container from a second host terminal:

```bash
docker compose -f docker-compose.fake.yml exec tracking bash
```

Then run ROS inspection commands such as `ros2 node list` **inside the container**.

Run automated tests on the **host / WSL Ubuntu shell**:

```bash
cd ~/object_tracking
source /opt/ros/jazzy/setup.bash
cd objtrk_ws
colcon build --symlink-install
source install/setup.bash
colcon test --event-handlers console_direct+
colcon test-result --verbose
```

Run static checks on the **host / WSL shell from the repository root**:

```bash
cd ~/object_tracking
pre-commit run --all-files
```
