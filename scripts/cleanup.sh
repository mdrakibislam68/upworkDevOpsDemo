#!/usr/bin/env bash
# scripts/cleanup.sh — Stop and remove project containers and the project network.
#
# Usage:
#   bash scripts/cleanup.sh
#
# Safety notes:
#   - Only removes containers and the network that belong to THIS project.
#   - Does NOT run 'docker system prune' or any global cleanup command.
#   - Does NOT remove Docker volumes or images by default.
#   - Passes --remove-orphans to Compose to clean up any leftover containers.
#
# To also remove built images, run:
#   docker compose down --rmi local

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${BOLD}[cleanup]${RESET} $*"; }
success() { echo -e "${GREEN}[cleanup]${RESET} $*"; }
warn()    { echo -e "${YELLOW}[cleanup]${RESET} $*"; }
error()   { echo -e "${RED}[cleanup] ERROR:${RESET} $*" >&2; }
die()     { error "$*"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

command -v docker >/dev/null 2>&1 \
  || die "Docker is not installed or not in PATH."
docker compose version >/dev/null 2>&1 \
  || die "'docker compose' (Compose v2) is not available."

info "Stopping and removing project containers…"
docker compose down --remove-orphans

success "Project containers stopped and removed."

# Check if the project network still exists and remove it if so.
NETWORK_NAME="demo-app-net"
if docker network inspect "${NETWORK_NAME}" >/dev/null 2>&1; then
  info "Removing Docker network '${NETWORK_NAME}'…"
  docker network rm "${NETWORK_NAME}" 2>/dev/null \
    && success "Network '${NETWORK_NAME}' removed." \
    || warn "Could not remove network '${NETWORK_NAME}' (it may still be in use)."
else
  info "Network '${NETWORK_NAME}' does not exist — nothing to remove."
fi

echo
success "Cleanup complete. No other Docker resources were modified."
info "To also remove the project Docker images, run:"
echo "  docker compose down --rmi local"

