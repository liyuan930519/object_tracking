ARG ROS_DISTRO=jazzy

FROM ros:${ROS_DISTRO}-ros-base

ARG ROS_DISTRO

SHELL ["/bin/bash", "-c"]

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /workspace

# Copy only the ROS workspace source tree.
COPY objtrk_ws/src ./src

# Ubuntu 24.04 (Noble) uses ubuntu.sources.
#
# Use HTTPS instead of HTTP because some networks/proxies are unreliable
# when accessing archive.ubuntu.com/security.ubuntu.com over port 80.
#
# Retry transient package repository failures before giving up.
RUN sed -i \
        -e 's|http://archive.ubuntu.com/ubuntu|https://archive.ubuntu.com/ubuntu|g' \
        -e 's|http://security.ubuntu.com/ubuntu|https://security.ubuntu.com/ubuntu|g' \
        /etc/apt/sources.list.d/ubuntu.sources \
    && apt-get \
        -o Acquire::Retries=5 \
        -o Acquire::https::Timeout=30 \
        update \
    && rosdep update --rosdistro "${ROS_DISTRO}" \
    && rosdep install \
        --from-paths src \
        --ignore-src \
        --rosdistro "${ROS_DISTRO}" \
        --as-root apt:true \
        -r \
        -y \
    && rm -rf /var/lib/apt/lists/*

# Build the ROS workspace.
RUN source "/opt/ros/${ROS_DISTRO}/setup.bash" \
    && colcon build --symlink-install

COPY docker/entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

CMD ["ros2", "launch", "tracking_bringup", "tracking.launch.py"]
