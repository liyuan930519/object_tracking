# ROS 2 Object Tracking

A containerized ROS 2 object-tracking system built with **ROS 2 Jazzy**, **Python**, and **OpenCV**.

The system separates image acquisition from tracking: one ROS node publishes camera images, and a second node detects the largest valid red object and publishes its visibility and image-space centroid.

The default runtime uses a physical webcam. A deterministic fake camera is included for automated tests and Docker smoke testing without hardware.

---

## Architecture

```text
CameraNode
  └─ /camera/image_raw  (sensor_msgs/msg/Image)
          ↓
TrackerNode
  └─ /tracker/object_state  (objtrk_interfaces/msg/ObjectState)
```

Packages:

- `camera_pkg`: camera node and real/fake camera sources
- `tracker_pkg`: tracker node and red-object detector
- `objtrk_interfaces`: custom tracking-result message
- `tracking_bringup`: launch files, YAML configuration, and system test

The source code uses relative topic names, which resolve to the paths above in the root namespace while remaining compatible with ROS namespaces/remapping.

### Tracking output

`objtrk_interfaces/msg/ObjectState.msg`:

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

A valid message is still published so downstream components do not need to infer target loss from a missing message.

---

## Tracking Approach

`RedObjectDetector`:

1. converts BGR to HSV;
2. thresholds two red hue ranges;
3. combines the masks;
4. applies morphological opening/closing;
5. finds external contours;
6. selects the largest contour;
7. rejects contours below `min_area`;
8. calculates the centroid using image moments.

If multiple red regions are present, only the largest valid region is reported.

The detector is isolated from ROS communication so image-processing behavior can be unit tested independently.

---

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

uses the same image settings with `camera_mode: fake`.

| Parameter | Default | Runtime behavior |
|---|---:|---|
| `camera_mode` | `real` | startup-only while running |
| `device_path` | `/dev/video0` | startup-only while running |
| `width` | `640` | startup-only while running |
| `height` | `480` | startup-only while running |
| `fps` | `10.0` | dynamic |
| `frame_id` | `camera` | dynamic |
| `min_area` | `300.0` | dynamic |

Examples:

```bash
ros2 param set /camera_node fps 5.0
ros2 param set /tracker_node min_area 500.0
```

---

## Command Execution Context

- **Repository root**: `~/object_tracking`
- **ROS workspace root**: `~/object_tracking/objtrk_ws`
- `docker compose`, Git, `pipx`, and `pre-commit` commands run on the **host / WSL shell**.
- `colcon build` and `colcon test` run from the **ROS workspace root** after sourcing ROS 2.
- ROS inspection commands for the Docker smoke test run **inside the running container** after `docker compose ... exec tracking bash`.

---

## Docker Build

Prerequisites:

- Docker
- Docker Compose
- native Linux + V4L2 webcam for physical-camera operation

From the repository root:

```bash
cd ~/object_tracking
docker compose build
```

The image is based on `ros:jazzy-ros-base`, dependencies are resolved with `rosdep`, and the workspace is built with `colcon build --symlink-install`.

---

## Run With a Physical Camera

The production configuration uses `camera_mode: real`.

On native Linux, identify video devices with:

```bash
ls -l /dev/video*
```

or:

```bash
v4l2-ctl --list-devices
```

Default:

```bash
cd ~/object_tracking
docker compose up
```

Compose maps the selected host camera to `/dev/video0` inside the container.

If the host camera is `/dev/video2`:

```bash
CAMERA_DEVICE=/dev/video2 docker compose up
```

The ROS configuration still uses:

```yaml
device_path: /dev/video0
```

because the host-specific device number is handled by Docker.

### Camera failure behavior

If the camera cannot be opened, a clear error is logged and the camera executable exits with a non-zero code.

If frame capture fails after startup, the source is closed, ROS shutdown is requested, and the executable exits as a failure.

Normal shutdown is handled without intentionally printing a noisy traceback.

---

## Target FPS and Observed Throughput

The configured `fps` is a **target rate**, not a hard real-time guarantee.

Actual throughput depends on:

- image resolution;
- camera/backend performance;
- CPU availability;
- image conversion;
- ROS 2/DDS serialization and transport;
- tracker processing;
- Docker/WSL overhead and scheduler load.

During development under WSL2:

```text
160 x 120  -> stable at approximately 10 Hz
640 x 480  -> effective rate below the configured 10 Hz
```

The production configuration keeps `640x480 @ 10 FPS` as a target rather than claiming that 10 Hz is guaranteed on every device.

A different machine, native Linux environment, camera backend, or transport configuration may produce different results.

For production use, effective FPS and end-to-end latency should be measured rather than inferred from the configured timer period.

---

## Fake-Camera Docker Smoke Test

For environments without direct webcam access:

```bash
cd ~/object_tracking
docker compose -f docker-compose.fake.yml up
```

Keep that terminal running.

In another host / WSL terminal:

```bash
cd ~/object_tracking
docker compose -f docker-compose.fake.yml exec tracking bash
```

The following commands run **inside the container**.

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

Verify tracking output:

```bash
ros2 topic echo /tracker/object_state
```

The fake camera generates a moving red circle, so `visible` should normally be `true` with finite `x`/`y` coordinates.

This validates the containerized software path:

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

This smoke test was executed successfully during development.

---

## Automated Test Strategy

Automated tests do **not** depend on a physical camera.

The repository contains **13 `test_*` cases** across unit, ROS integration, and end-to-end system levels.

The layered design is intentional:

```text
camera-source unit tests
        +
detector unit tests
        ↓
tracker ROS integration tests
        ↓
CameraNode -> TrackerNode system test
```

This makes failures easier to localize.

### Fake camera unit tests

File: `objtrk_ws/src/camera_pkg/test/test_fake_camera.py`

| Test function | Design purpose |
|---|---|
| `test_fake_camera_returns_image()` | Normal source path: verifies a valid BGR frame containing the synthetic red target. |
| `test_closed_fake_camera_cannot_read()` | Lifecycle/error path: a closed source returns `(False, None)`. |
| `test_fake_camera_rejects_invalid_dimensions()` | Configuration validation: invalid dimensions raise `ValueError`. |

### Detector unit tests

File: `objtrk_ws/src/tracker_pkg/test/test_detector.py`

| Test function | Design purpose |
|---|---|
| `test_detects_red_object()` | Normal tracking case: known target -> expected visibility and centroid. |
| `test_no_object_returns_not_visible()` | No-target behavior: `visible=False`, `x/y=NaN`. |
| `test_object_below_min_area_is_not_visible()` | Small regions below `min_area` are ignored. |
| `test_empty_image_raises_value_error()` | Empty input is rejected explicitly. |
| `test_invalid_image_shape_raises_value_error()` | Non-BGR-shaped input is rejected. |
| `test_invalid_min_area_raises_value_error()` | Non-positive threshold is rejected. |
| `test_selects_largest_red_object()` | Multiple candidates -> deterministic largest-object selection. |

### Tracker ROS integration tests

File: `objtrk_ws/src/tracker_pkg/test/test_tracker_node.py`

These tests use real ROS pub/sub rather than invoking the callback directly.

| Test function | Design purpose |
|---|---|
| `test_tracker_node_publishes_detection(tracker_harness)` | Verifies normal Image -> TrackerNode -> ObjectState behavior, centroid, and `frame_id`. |
| `test_tracker_node_reports_not_visible(tracker_harness)` | Verifies a valid invisible state is still published when no target exists. |

`spin_until(...)`, `tracker_harness()`, and `publish_image_and_wait_for_state(...)` are support utilities, not independent tests.

### End-to-end ROS system test

File: `objtrk_ws/src/tracking_bringup/test/test_tracking_system.py`

```python
def test_fake_camera_to_tracker_end_to_end():
```

Purpose: validate the complete ROS pipeline without manually injecting an image into the tracker.

It verifies:

- fake-camera parameters are accepted;
- `CameraNode.start()` succeeds;
- publishers are discovered;
- image and tracking messages are produced;
- image dimensions and encoding are correct;
- the fake target is detected;
- coordinates are finite and within image bounds;
- `frame_id` is propagated to `ObjectState.header`.

### Test summary

| Level | File | Count |
|---|---|---:|
| Camera-source unit | `test_fake_camera.py` | 3 |
| Detector unit | `test_detector.py` | 7 |
| Tracker ROS integration | `test_tracker_node.py` | 2 |
| End-to-end ROS system | `test_tracking_system.py` | 1 |
| **Total** |  | **13** |

---

## Run Automated Tests

Run on the host / WSL Ubuntu shell:

```bash
cd ~/object_tracking
source /opt/ros/jazzy/setup.bash
cd objtrk_ws

colcon build --symlink-install
source install/setup.bash

colcon test --event-handlers console_direct+
colcon test-result --verbose
```

---

## Pre-commit

`pre-commit` is installed on the **host / WSL environment**, not inside the application container.

Install with `pipx`:

```bash
sudo apt update
sudo apt install -y pipx
pipx ensurepath
pipx install pre-commit
```

Then from the repository root:

```bash
cd ~/object_tracking
pre-commit install
pre-commit run --all-files
```

Configured checks include repository hygiene, YAML/XML validation, Ruff linting, and Ruff formatting.

If a hook modifies files, review the changes and run `pre-commit run --all-files` again until all checks pass.

---

## System-Level Limitations and Future Improvements

The main improvement areas are system-level because the detector is only one replaceable component in the pipeline.

### Observability and performance

The current system does not expose explicit performance metrics.

A production implementation should measure:

- effective camera FPS;
- tracker processing rate;
- image-to-result latency;
- dropped/stale frames;
- processing failures;
- camera health.

The measured resolution/FPS behavior above is an example of why observed runtime metrics are preferable to assuming the configured rate is achieved.

### Backpressure and overload behavior

The current implementation does not define an explicit policy for cases where image production exceeds downstream processing capacity.

A production system should define whether to:

- drop stale frames;
- process only the latest frame;
- use bounded queues;
- monitor queueing latency;
- reduce the source rate.

### Failure recovery and supervision

The current implementation fails explicitly on camera errors.

Possible production improvements include:

- bounded reopen attempts with backoff;
- process/container restart policies;
- health/readiness checks;
- ROS diagnostics;
- structured error counters and logs.

### Test strategy and CI

The current hierarchy covers unit tests, ROS integration, end-to-end fake-camera testing, and a manual container smoke test.

A production CI pipeline could additionally:

- run pre-commit automatically;
- build from a clean ROS environment;
- run all automated tests;
- build the Docker image;
- automate the fake-camera container smoke test;
- run physical-camera hardware-in-the-loop tests on a native Linux/V4L2 runner.

Keeping physical hardware tests separate preserves deterministic hardware-independent CI.

### Deployment and configuration

The current design separates host-specific camera paths from the application-visible `/dev/video0`.

Further system-level improvements could include:

- hardware-specific deployment profiles;
- CPU/memory limits;
- restart policies;
- configuration versioning;
- centralized metrics/logging;
- multiple namespaced camera/tracker instances.

### Component boundaries

`CameraSource` isolates hardware capture from `CameraNode`, and `RedObjectDetector` isolates perception logic from `TrackerNode`.

This means the camera implementation or tracking algorithm can be replaced without changing the ROS message contract.

### Tracking-specific limitations

The current perception algorithm is intentionally simple:

- fixed HSV thresholds are lighting-sensitive;
- unrelated red objects can cause false positives;
- only the largest valid region is selected;
- no persistent track ID or temporal model is used;
- occlusion and multi-object tracking are not handled;
- no confidence score is published.

These are known limitations, but the focus of this exercise is the system structure, robustness, testability, configuration, and deployment boundaries around the tracking component.

---

## Development Environment Limitation: Physical Webcam on WSL2

Development and container smoke testing were performed under **WSL2**.

Direct physical webcam `/dev/video*` access was not available, so this exact path was not directly validated:

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

---

## Quick Reference

Repository root:

```bash
cd ~/object_tracking
```

Build:

```bash
docker compose build
```

Run with default physical camera on native Linux:

```bash
docker compose up
```

Run with another host camera:

```bash
CAMERA_DEVICE=/dev/video2 docker compose up
```

Run fake-camera smoke test:

```bash
docker compose -f docker-compose.fake.yml up
```

Run tests:

```bash
source /opt/ros/jazzy/setup.bash
cd objtrk_ws
colcon build --symlink-install
source install/setup.bash
colcon test --event-handlers console_direct+
colcon test-result --verbose
```

Run static checks:

```bash
cd ~/object_tracking
pre-commit run --all-files
```
