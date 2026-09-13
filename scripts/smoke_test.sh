#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

COMPOSE_FILE="${COMPOSE_FILE:-${REPO_ROOT}/docker-compose.fake.yml}"
SERVICE="${SERVICE:-tracking}"
SMOKE_TIMEOUT="${SMOKE_TIMEOUT:-30}"
OBSERVER="${SCRIPT_DIR}/smoke_observer.py"

cd "${REPO_ROOT}"

if [[ ! -f "${COMPOSE_FILE}" ]]; then
    echo "ERROR: Compose file not found: ${COMPOSE_FILE}" >&2
    exit 2
fi

if [[ ! -f "${OBSERVER}" ]]; then
    echo "ERROR: Smoke observer not found: ${OBSERVER}" >&2
    exit 2
fi

CONTAINER_ID="$(docker compose -f "${COMPOSE_FILE}" ps -q "${SERVICE}")"

if [[ -z "${CONTAINER_ID}" ]]; then
    echo "ERROR: No existing container found for service '${SERVICE}'." >&2
    echo "Start it first, for example:" >&2
    echo "  docker compose -f docker-compose.fake.yml up -d" >&2
    exit 1
fi

if [[ "$(docker inspect -f '{{.State.Running}}' "${CONTAINER_ID}")" != "true" ]]; then
    echo "ERROR: Container for service '${SERVICE}' exists but is not running." >&2
    exit 1
fi

echo "Attaching smoke observer to the already-running deployment..."
echo "Container: ${CONTAINER_ID}"
echo "The application container will NOT be stopped or restarted."

set +e
docker compose -f "${COMPOSE_FILE}" exec -T "${SERVICE}"     bash -lc     "source /opt/ros/\${ROS_DISTRO}/setup.bash &&      source /workspace/install/setup.bash &&      python3 - --timeout ${SMOKE_TIMEOUT}"     < "${OBSERVER}"
STATUS=$?
set -e

if [[ ${STATUS} -eq 0 ]]; then
    echo "Attach-only smoke test completed successfully."
    echo "Application container remains running."
else
    echo "Attach-only smoke test failed with exit code ${STATUS}." >&2
    echo "Application container remains running." >&2
fi

exit "${STATUS}"
