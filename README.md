# ROS 2 Object Tracking

A containerized ROS 2 object-tracking system built with **ROS 2 Jazzy**, **Python**, and **OpenCV**.

The system separates image acquisition from tracking:

```text
CameraSource
    ↓
CameraNode
    ↓
/camera/image_raw
    ↓
TrackerNode
    ↓
/tracker/object_state
```

The default runtime uses a physical webcam. A deterministic fake camera is provided for hardware-independent testing and Docker smoke validation.

---

## Architecture

ROS packages:

```text
objtrk_ws/src/
├── camera_pkg/
├── objtrk_interfaces/
├── tracker_pkg/
└── tracking_bringup/
```

- `camera_pkg`: camera node plus real/fake camera-source implementations
- `tracker_pkg`: tracker node and red-object detector
- `objtrk_interfaces`: custom `ObjectState` message
- `tracking_bringup`: launch files, configuration, and system test

The code uses relative ROS topic names. In the default root namespace they resolve to:

```text
/camera/image_raw
/tracker/object_state
```

Using relative names keeps the nodes compatible with ROS namespaces and remapping.

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

A valid message is still published so downstream components do not need to infer target loss from missing output.

---

## Tracking Approach

`RedObjectDetector` uses a simple OpenCV pipeline:

1. convert BGR to HSV;
2. threshold two red hue ranges;
3. combine the masks;
4. apply morphological opening/closing;
5. find external contours;
6. select the largest contour;
7. reject it if its area is below `min_area`;
8. calculate the centroid using image moments.

The detector is intentionally isolated from ROS communication so image-processing logic can be unit tested independently.

---

## Configuration

Production configuration:

```text
objtrk_ws/src/tracking_bringup/config/tracking.yaml
```

Default camera parameters:

```yaml
camera_mode: real
device_path: /dev/video0
width: 640
height: 480
fps: 10.0
frame_id: camera
```

Default tracker parameter:

```yaml
min_area: 300.0
```

Fake-camera configuration:

```text
objtrk_ws/src/tracking_bringup/config/tracking_fake.yaml
```

uses the same basic image settings with:

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

Runtime-safe examples:

```bash
ros2 param set /camera_node fps 5.0
ros2 param set /tracker_node min_area 500.0
```

---

## Command Execution Context

- **Repository root**: `~/object_tracking`
- **ROS workspace root**: `~/object_tracking/objtrk_ws`
- `docker compose`, `docker run`, Git, `pipx`, and `pre-commit` commands run on the **host / WSL shell**.
- The recommended reviewer workflow runs Layers 1–3 in a disposable container created from the application image.
- Host-side `colcon` commands are an optional developer workflow and require ROS 2 Jazzy on the host.
- Layer 4 is an attach-only smoke test against an already-running application container.

---

## Docker Build

Prerequisites for the main reviewer workflow:

- Docker
- Docker Compose

From the repository root:

```bash
cd ~/object_tracking
docker compose build
```

The Dockerfile:

- starts from `ros:jazzy-ros-base`;
- installs package dependencies with `rosdep`;
- builds the ROS workspace with `colcon`;
- uses `docker/entrypoint.sh` to source ROS and the built workspace at runtime.

The resulting image is:

```text
object-tracking:jazzy
```

---

## Run With a Physical Camera

The production configuration uses `camera_mode: real`.

On native Linux, identify available video devices with:

```bash
ls -l /dev/video*
```

or:

```bash
v4l2-ctl --list-devices
```

Run with the default host camera:

```bash
cd ~/object_tracking
docker compose up
```

Compose maps the selected host camera to `/dev/video0` inside the container.

If the host camera is `/dev/video2`:

```bash
CAMERA_DEVICE=/dev/video2 docker compose up
```

The ROS configuration can still use:

```yaml
device_path: /dev/video0
```

because host-specific device selection is handled by Docker.

### Camera failure behavior

If the camera cannot be opened, the node logs a clear error and exits non-zero.

If frame capture fails after startup, the source is closed, ROS shutdown is requested, and the executable exits as a failure.

Normal shutdown is handled without intentionally producing a noisy traceback.

---

## Target FPS and Observed Throughput

The configured `fps` is a **target rate**, not a hard real-time guarantee.

Actual throughput depends on image resolution, camera/backend performance, CPU load, image conversion, ROS 2/DDS serialization and transport, and the runtime environment.

Observed during development under WSL2:

```text
160 x 120  -> stable at approximately 10 Hz
640 x 480  -> effective rate below the configured 10 Hz
```

The production configuration keeps `640x480 @ 10 FPS` as a target rather than claiming a guaranteed rate on every device.

A production system should expose measured FPS and end-to-end latency as runtime metrics.

---

## Test Strategy

The test structure separates pre-deployment verification from post-deployment verification:

```text
Pre-deployment
├── Layer 1: Unit tests
├── Layer 2: ROS integration tests
└── Layer 3: In-process system test

Post-deployment
└── Layer 4: Attach-only Docker smoke test

Future
└── Layer 5: Hardware-in-the-loop
```

Layers 1–3 run in an **isolated test environment**, meaning no already-running application nodes share the same ROS graph.

For reviewers, the recommended isolated environment is a disposable container created from the built application image.

Layer 4 validates the already-running deployment through its public ROS interfaces without recreating `CameraNode` or `TrackerNode`.

### Automated tests: Layers 1–3

The repository contains **13 `test_*` cases**:

| Layer | File | Count | Main purpose |
|---|---|---:|---|
| Unit | `camera_pkg/test/test_fake_camera.py` | 3 | source lifecycle, synthetic image, invalid dimensions |
| Unit | `tracker_pkg/test/test_detector.py` | 7 | detection, no target, thresholds, invalid inputs, largest target |
| ROS integration | `tracker_pkg/test/test_tracker_node.py` | 2 | external Image publisher -> TrackerNode -> ObjectState |
| In-process system | `tracking_bringup/test/test_tracking_system.py` | 1 | FakeCamera -> CameraNode -> TrackerNode end-to-end |
| **Total** |  | **13** | |

These tests do not require a physical camera.

### Reviewer workflow: run Layers 1–3 in Docker

Build the image:

```bash
cd ~/object_tracking
docker compose build
```

Run the 13 tests in a disposable container:

```bash
docker run --rm object-tracking:jazzy \
  bash -lc '
    source /opt/ros/jazzy/setup.bash &&
    source /workspace/install/setup.bash &&
    cd /workspace &&
    colcon test --event-handlers console_direct+ &&
    colcon test-result --verbose
  '
```

The temporary container is removed automatically when the command exits.

This is the recommended reviewer path because the host does not need a separate ROS 2 Jazzy installation.

### Optional developer workflow: host-side tests

Developers with ROS 2 Jazzy installed can run the same Layers 1–3 directly:

```bash
cd ~/object_tracking
source /opt/ros/jazzy/setup.bash
cd objtrk_ws

colcon build --symlink-install
source install/setup.bash

colcon test --event-handlers console_direct+
colcon test-result --verbose
```

Do not run these integration/system tests inside an application container that is already running `CameraNode` and `TrackerNode`; duplicate nodes and shared topic traffic can make the test graph non-deterministic.

---

## Attach-Only Docker Smoke Test

Layer 4 validates an **already-running** fake-camera deployment.

Files:

```text
scripts/
├── smoke_test.sh
└── smoke_observer.py
```

Start the deployment:

```bash
cd ~/object_tracking
docker compose -f docker-compose.fake.yml up -d
```

Ensure the script is executable:

```bash
chmod +x scripts/smoke_test.sh
```

Run the smoke test:

```bash
./scripts/smoke_test.sh
```

The script does **not** build, start, restart, or stop the application container.

It verifies that the `tracking` service is already running, then streams `smoke_observer.py` to a temporary Python process inside that container.

The observer does not create application nodes. It creates only `/smoke_observer` and checks:

- `/camera_node` and `/tracker_node` are present;
- `/camera/image_raw` is actively publishing valid `bgr8` images;
- `/tracker/object_state` is being published;
- the fake target is visible;
- `x` and `y` are finite and inside image bounds;
- image and tracking `frame_id` values are valid and consistent.

A successful run prints:

```text
SMOKE TEST PASS
...
Attach-only smoke test completed successfully.
Application container remains running.
```

This attach-only smoke test was executed successfully during development.

Confirm the application still runs:

```bash
docker compose -f docker-compose.fake.yml ps
```

Stop it explicitly when finished:

```bash
docker compose -f docker-compose.fake.yml down
```

For manual debugging:

```bash
docker compose -f docker-compose.fake.yml exec tracking bash
```

then, for example:

```bash
ros2 node list
ros2 topic list
ros2 topic hz /camera/image_raw
ros2 topic echo /tracker/object_state
```

---

## Pre-commit

`pre-commit` is a host-side development tool.

Install with `pipx`:

```bash
sudo apt update
sudo apt install -y pipx
pipx ensurepath
pipx install pre-commit
```

From the repository root:

```bash
cd ~/object_tracking
pre-commit install
pre-commit run --all-files
```

Configured checks include repository hygiene, YAML/XML validation, Ruff linting, and Ruff formatting.

---

## System-Level Limitations and Future Improvements

### Runtime performance

The configured camera FPS is a target rather than a guaranteed measured rate. The observed rate changes with image resolution and runtime environment.

A production system should expose measured publication rate and end-to-end latency so performance can be characterized on the target hardware.

### Failure handling

The current camera path fails explicitly: camera open/read failures are logged and result in a non-zero process exit rather than silent failure.

If longer-running self-recovery were required, a reasonable next step would be bounded camera reopen attempts with backoff.

### Test and CI evolution

The current test strategy covers unit, ROS integration, in-process system, and attach-only post-deployment smoke validation.

The Layer 4 smoke test intentionally covers one core deployment scenario. If deployment-level checks grow, the observer logic could move into a **pytest-based black-box suite** with shared ROS fixtures and multiple independent scenarios, preferably executed from a separate test container or CI job.

The remaining hardware-dependent path should be validated on native Linux with a real V4L2 webcam as a hardware-in-the-loop test.

### Tracking-specific limitations

The tracking algorithm is intentionally simple:

- fixed HSV thresholds are sensitive to lighting and camera color response;
- unrelated red objects may produce false positives;
- only the largest valid red region is reported.

The detector is isolated from the ROS transport layer, so a different perception implementation can replace it without changing the surrounding system interface.

---

## Optional Extensions

### Multiple cameras

The current nodes use relative topic names and configurable camera device paths. Additional camera/tracker pairs could therefore be instantiated under separate ROS namespaces, each with its own device mapping and parameter file.

Conceptually:

```text
/dev/video0 -> /camera1/camera/image_raw -> /camera1/tracker/object_state
/dev/video1 -> /camera2/camera/image_raw -> /camera2/tracker/object_state
```

### Multiple objects

The current detector and `ObjectState` interface intentionally represent one target.

Multi-object support would require the detector to return multiple valid detections and the ROS output contract to publish an array/list of object states. Persistent track IDs would only be required if cross-frame object identity were part of the requirement.

### More production-like deployment

The current design already separates host-specific device mapping, container-visible device paths, ROS application configuration, and pre-/post-deployment verification.

A production deployment could preserve these boundaries while adding environment-specific configuration and operational supervision as required.

---

## Hardware Validation Boundary: Physical Webcam on WSL2

Development and container smoke testing were performed under **WSL2**.

Direct physical `/dev/video*` webcam access was not available, so this exact path was not directly validated:

```text
physical webcam
    ↓
host /dev/video*
    ↓
Docker device passthrough
    ↓
container /dev/video0
    ↓
OpenCVCameraSource
```

The production Compose configuration follows the normal native-Linux V4L2 device-mapping model.

The complete containerized software pipeline was validated with `FakeCameraSource`.

Physical-camera passthrough should therefore be verified on a native Linux host with V4L2 access.

---

## Quick Reference

From the repository root:

```bash
cd ~/object_tracking
```

Build:

```bash
docker compose build
```

Run Layers 1–3 in a disposable test container:

```bash
docker run --rm object-tracking:jazzy \
  bash -lc '
    source /opt/ros/jazzy/setup.bash &&
    source /workspace/install/setup.bash &&
    cd /workspace &&
    colcon test --event-handlers console_direct+ &&
    colcon test-result --verbose
  '
```

Start fake deployment:

```bash
docker compose -f docker-compose.fake.yml up -d
```

Run Layer 4 smoke test:

```bash
./scripts/smoke_test.sh
```

Stop fake deployment when finished:

```bash
docker compose -f docker-compose.fake.yml down
```

Run production configuration on native Linux:

```bash
docker compose up
```

Use another host camera:

```bash
CAMERA_DEVICE=/dev/video2 docker compose up
```

Run static checks:

```bash
pre-commit run --all-files
```
