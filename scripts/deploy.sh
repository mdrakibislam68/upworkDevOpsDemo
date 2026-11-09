#!/usr/bin/env bash
# scripts/deploy.sh — Build images and start the project stack.
#
# Usage:
#   bash scripts/deploy.sh
#
# What this script does:
#   1. Checks required tools are installed.
#   2. Creates .env from .env.example if .env does not exist.
#   3. Validates the Compose configuration.
#   4. Builds Docker images.
#   5. Starts services in detached mode.
#   6. Waits for the health checks to pass.
#   7. Prints the application URL.
#
# This script does NOT promise zero-downtime deployment or automatic rollback.
# For production use, consider a more sophisticated deployment strategy.

set -euo pipefail

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${BOLD}[deploy]${RESET} $*"; }
success() { echo -e "${GREEN}[deploy]${RESET} $*"; }
warn()    { echo -e "${YELLOW}[deploy]${RESET} $*"; }
error()   { echo -e "${RED}[deploy] ERROR:${RESET} $*" >&2; }
die()     { error "$*"; exit 1; }

# ---------------------------------------------------------------------------
# Locate project root (parent of this script's directory)
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

# ---------------------------------------------------------------------------
# Step 1 — Check required tools
# ---------------------------------------------------------------------------
info "Checking required tools…"
for cmd in docker; do
  command -v "${cmd}" >/dev/null 2>&1 \
    || die "'${cmd}' is not installed or not in PATH. Please install Docker."
done

docker compose version >/dev/null 2>&1 \
  || die "'docker compose' (Compose v2) is not available. Please upgrade Docker."

success "All required tools found."

# ---------------------------------------------------------------------------
# Step 2 — Create .env from .env.example if missing
# ---------------------------------------------------------------------------
if [[ ! -f ".env" ]]; then
  if [[ -f ".env.example" ]]; then
    cp ".env.example" ".env"
    warn ".env not found — created from .env.example. Review it before continuing."
  else
    warn ".env.example missing; proceeding with Compose defaults."
  fi
else
  info ".env already exists; using existing values."
fi

# Load NGINX_PORT so we can print the URL later.
NGINX_PORT="${NGINX_PORT:-8080}"
if [[ -f ".env" ]]; then
  # Source only lines that look like VARNAME=value (no subshell execution).
  while IFS='=' read -r key value; do
    [[ "${key}" =~ ^[A-Z_][A-Z0-9_]*$ ]] && export "${key}=${value}" 2>/dev/null || true
  done < <(grep -E '^[A-Z_][A-Z0-9_]*=' .env || true)
fi
NGINX_PORT="${NGINX_PORT:-8080}"

# ---------------------------------------------------------------------------
# Step 3 — Validate Compose configuration
# ---------------------------------------------------------------------------
info "Validating Compose configuration…"
docker compose config --quiet \
  || die "Compose configuration is invalid. Fix compose.yaml before deploying."
success "Compose configuration is valid."

# ---------------------------------------------------------------------------
# Step 4 — Build images
# ---------------------------------------------------------------------------
info "Building Docker images (this may take a few minutes on first run)…"
docker compose build --pull \
  || die "Image build failed. Check the Dockerfiles and try again."
success "Images built successfully."

# ---------------------------------------------------------------------------
# Step 5 — Start services
# ---------------------------------------------------------------------------
info "Starting services…"
docker compose up --detach \
  || die "Failed to start services. Run 'docker compose logs' to investigate."
success "Services started."

# ---------------------------------------------------------------------------
# Step 6 — Wait for health checks
# ---------------------------------------------------------------------------
info "Waiting for containers to become healthy (up to 90 seconds)…"

TIMEOUT=90
ELAPSED=0
INTERVAL=5

while [[ "${ELAPSED}" -lt "${TIMEOUT}" ]]; do
  NGINX_HEALTH="$(docker inspect --format '{{.State.Health.Status}}' demo-nginx-proxy 2>/dev/null || echo 'unknown')"
  WEBAPP_HEALTH="$(docker inspect --format '{{.State.Health.Status}}' demo-webapp      2>/dev/null || echo 'unknown')"

  if [[ "${NGINX_HEALTH}" == "healthy" && "${WEBAPP_HEALTH}" == "healthy" ]]; then
    success "All containers are healthy."
    break
  fi

  echo "    nginx: ${NGINX_HEALTH}  |  webapp: ${WEBAPP_HEALTH}  (${ELAPSED}s elapsed)"
  sleep "${INTERVAL}"
  ELAPSED=$(( ELAPSED + INTERVAL ))
done

if [[ "${NGINX_HEALTH}" != "healthy" || "${WEBAPP_HEALTH}" != "healthy" ]]; then
  warn "One or more containers did not reach healthy state within ${TIMEOUT}s."
  warn "Current status: nginx=${NGINX_HEALTH}  webapp=${WEBAPP_HEALTH}"
  warn "Run 'docker compose logs' to investigate. The stack may still be starting."
fi

# ---------------------------------------------------------------------------
# Step 7 — Print status
# ---------------------------------------------------------------------------
echo
success "Deployment complete."
echo -e "  ${BOLD}Application URL${RESET}: http://localhost:${NGINX_PORT}/"
echo -e "  ${BOLD}Health endpoint${RESET}: http://localhost:${NGINX_PORT}/healthz"
echo
info "Useful commands:"
echo "  docker compose ps          — container status"
echo "  docker compose logs -f     — follow all logs"
echo "  bash scripts/test.sh       — run automated tests"
echo "  bash scripts/cleanup.sh    — stop and remove containers"

