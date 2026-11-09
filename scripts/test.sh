#!/usr/bin/env bash
# scripts/test.sh — Run all static and live deployment tests.
#
# Usage:
#   bash scripts/test.sh
#
# This script delegates to the Python test suite in tests/test_deployment.py.
# It first performs a quick sanity check that Python 3 is available, then
# runs the tests and exits with the same exit code.

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BOLD='\033[1m'; RESET='\033[0m'

info()  { echo -e "${BOLD}[test]${RESET} $*"; }
error() { echo -e "${RED}[test] ERROR:${RESET} $*" >&2; }
die()   { error "$*"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

# --- Require Python 3 -------------------------------------------------------
command -v python3 >/dev/null 2>&1 \
  || die "python3 not found. Install Python 3.8+ and re-run."

PYTHON_VERSION="$(python3 -c 'import sys; print(sys.version_info.major, sys.version_info.minor)')"
read -r PY_MAJOR PY_MINOR <<<"${PYTHON_VERSION}"
if [[ "${PY_MAJOR}" -lt 3 || ( "${PY_MAJOR}" -eq 3 && "${PY_MINOR}" -lt 8 ) ]]; then
  die "Python 3.8+ required. Found: Python ${PY_MAJOR}.${PY_MINOR}"
fi

# --- Load NGINX_PORT if .env exists -----------------------------------------
if [[ -f ".env" ]]; then
  while IFS='=' read -r key value; do
    [[ "${key}" =~ ^[A-Z_][A-Z0-9_]*$ ]] && export "${key}=${value}" 2>/dev/null || true
  done < <(grep -E '^[A-Z_][A-Z0-9_]*=' .env || true)
fi

info "Running test suite…"
python3 tests/test_deployment.py
EXIT_CODE=$?

if [[ "${EXIT_CODE}" -eq 0 ]]; then
  echo -e "\n${GREEN}[test]${RESET} Test run complete. Exit code: ${EXIT_CODE}"
else
  echo -e "\n${RED}[test]${RESET} Test run finished with failures. Exit code: ${EXIT_CODE}"
fi

exit "${EXIT_CODE}"

