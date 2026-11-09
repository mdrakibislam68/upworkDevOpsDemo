#!/usr/bin/env python3
"""
tests/test_deployment.py — Automated deployment tests for docker-nginx-deployment.

Test groups
-----------
1. Static checks (always run, no Docker required)
   - Compose configuration syntax (docker compose config)
   - Nginx configuration syntax (nginx -t inside the proxy container)
   - Shell script syntax (bash -n)

2. Live HTTP tests (run when the stack is reachable)
   - GET / through Nginx → 200 and expected page content
   - GET /healthz → 200 and "ok" body
   - App port (3000) must NOT be reachable from the host

3. Docker state checks (run when Docker socket is available)
   - Both services reach healthy state within a timeout
   - App container does not publish any host port

Usage
-----
    python3 tests/test_deployment.py

Environment variables
---------------------
    NGINX_PORT   Host port to test (default: 8080)
    HEALTH_TIMEOUT  Seconds to wait for healthy state (default: 60)

Exit codes
----------
    0 — all executed tests passed
    1 — one or more tests failed or an error occurred
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PROJECT_ROOT   = Path(__file__).resolve().parent.parent
NGINX_PORT     = int(os.environ.get("NGINX_PORT", "8080"))
HEALTH_TIMEOUT = int(os.environ.get("HEALTH_TIMEOUT", "60"))
BASE_URL       = f"http://localhost:{NGINX_PORT}"
APP_PORT       = 3000   # Internal app port — must NOT be open on host.


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class colours:
    GREEN  = "\033[92m"
    RED    = "\033[91m"
    YELLOW = "\033[93m"
    RESET  = "\033[0m"
    BOLD   = "\033[1m"


def _c(colour: str, text: str) -> str:
    """Wrap text in ANSI colour if stdout is a TTY."""
    if sys.stdout.isatty():
        return colour + text + colours.RESET
    return text


results: list[dict] = []


def record(name: str, passed: bool | None, detail: str = "") -> None:
    """Record a test result and print it immediately."""
    if passed is True:
        icon  = _c(colours.GREEN, "PASS")
        label = "PASS"
    elif passed is False:
        icon  = _c(colours.RED,   "FAIL")
        label = "FAIL"
    else:  # None → skipped
        icon  = _c(colours.YELLOW, "SKIP")
        label = "SKIP"

    suffix = f"  {_c(colours.YELLOW, detail)}" if detail else ""
    print(f"  [{icon}] {name}{suffix}")
    results.append({"name": name, "status": label, "detail": detail})


def run(cmd: list[str], cwd: Path | None = None,
        timeout: int = 30) -> tuple[int, str, str]:
    """Run a subprocess, return (returncode, stdout, stderr)."""
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd or PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except FileNotFoundError:
        return -1, "", f"command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return -1, "", f"command timed out after {timeout}s"


def http_get(url: str, timeout: int = 10) -> tuple[int, str]:
    """Return (status_code, body) or (-1, error_message)."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, str(exc)
    except Exception as exc:
        return -1, str(exc)


def port_open(host: str, port: int, timeout: float = 2.0) -> bool:
    """Return True if a TCP connection can be established to host:port."""
    import socket
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def docker_available() -> bool:
    code, _, _ = run(["docker", "info"])
    return code == 0


def compose_available() -> bool:
    code, _, _ = run(["docker", "compose", "version"])
    return code == 0


# ---------------------------------------------------------------------------
# Test groups
# ---------------------------------------------------------------------------

def test_static_checks() -> None:
    """Group 1 — Static validation; no running containers required."""
    print(_c(colours.BOLD, "\n── Group 1: Static Checks ──────────────────────────────"))

    # 1a. Compose config validation
    if compose_available():
        code, out, err = run(["docker", "compose", "config", "--quiet"])
        passed = code == 0
        record("Compose config is valid (docker compose config)", passed,
               err.strip().splitlines()[0] if not passed and err else "")
    else:
        record("Compose config is valid (docker compose config)", None,
               "docker compose not available")

    # 1b. Shell script syntax — deploy.sh
    for script in ["scripts/deploy.sh", "scripts/test.sh", "scripts/cleanup.sh"]:
        path = PROJECT_ROOT / script
        if path.exists():
            code, _, err = run(["bash", "-n", str(path)])
            record(f"Shell syntax OK — {script}", code == 0,
                   err.strip().splitlines()[0] if err.strip() else "")
        else:
            record(f"Shell syntax OK — {script}", None, "file not found")

    # 1c. Python syntax of this test file itself
    code, _, err = run(["python3", "-m", "py_compile", str(Path(__file__))])
    record("Python syntax OK — tests/test_deployment.py", code == 0,
           err.strip() if err.strip() else "")

    # 1d. Required files exist
    required_files = [
        "compose.yaml",
        "Dockerfile.nginx",
        "app/Dockerfile",
        "nginx/default.conf",
        "app/index.html",
        ".env.example",
        ".gitignore",
        "README.md",
        "SECURITY.md",
    ]
    for rel in required_files:
        path = PROJECT_ROOT / rel
        record(f"Required file exists — {rel}", path.is_file())


def test_docker_state() -> None:
    """Group 2 — Docker container state checks."""
    print(_c(colours.BOLD, "\n── Group 2: Docker Container State ─────────────────────"))

    if not docker_available():
        record("Docker daemon reachable", None, "Docker not available; skipping group")
        return

    record("Docker daemon reachable", True)

    # 2a. Wait for services to become healthy.
    deadline = time.monotonic() + HEALTH_TIMEOUT
    healthy  = {"nginx": False, "webapp": False}

    print(f"     Waiting up to {HEALTH_TIMEOUT}s for containers to be healthy…", flush=True)
    while time.monotonic() < deadline:
        for svc in list(healthy.keys()):
            if healthy[svc]:
                continue
            code, out, _ = run([
                "docker", "inspect",
                "--format", "{{.State.Health.Status}}",
                f"demo-{svc}-proxy" if svc == "nginx" else f"demo-{svc}",
            ])
            status = out.strip()
            if status == "healthy":
                healthy[svc] = True
        if all(healthy.values()):
            break
        time.sleep(3)

    record("nginx container is healthy", healthy["nginx"],
           f"waited {HEALTH_TIMEOUT}s" if not healthy["nginx"] else "")
    record("webapp container is healthy", healthy["webapp"],
           f"waited {HEALTH_TIMEOUT}s" if not healthy["webapp"] else "")

    # 2b. webapp must NOT publish any host port.
    code, out, _ = run([
        "docker", "inspect", "--format",
        "{{json .NetworkSettings.Ports}}", "demo-webapp",
    ])
    if code == 0:
        try:
            ports = json.loads(out.strip())
            # Ports dict is null or all values are null when no host binding exists.
            exposed = any(
                bindings is not None
                for bindings in (ports or {}).values()
            )
            record("webapp has NO host-published ports", not exposed,
                   f"ports: {ports}" if exposed else "")
        except (json.JSONDecodeError, ValueError) as exc:
            record("webapp has NO host-published ports", False, str(exc))
    else:
        record("webapp has NO host-published ports", None,
               "Could not inspect container (is the stack running?)")


def test_http() -> None:
    """Group 3 — Live HTTP checks against the running stack."""
    print(_c(colours.BOLD, "\n── Group 3: HTTP / Endpoint Tests ──────────────────────"))

    if not port_open("localhost", NGINX_PORT):
        record(f"Nginx reachable on port {NGINX_PORT}", None,
               "Port not open — stack may not be running; skipping HTTP tests")
        return

    record(f"Nginx reachable on port {NGINX_PORT}", True)

    # 3a. Home page returns 200 and expected content.
    status, body = http_get(f"{BASE_URL}/")
    record("GET / returns HTTP 200", status == 200, f"got {status}" if status != 200 else "")
    expected_fragments = [
        "Docker",
        "Nginx",
        "Reverse Proxy",
    ]
    for fragment in expected_fragments:
        found = fragment.lower() in body.lower()
        record(f"Page body contains '{fragment}'", found,
               "fragment not found in response" if not found else "")

    # 3b. /healthz returns 200 and body "ok".
    h_status, h_body = http_get(f"{BASE_URL}/healthz")
    record("GET /healthz returns HTTP 200", h_status == 200,
           f"got {h_status}" if h_status != 200 else "")
    record("GET /healthz body is 'ok'", "ok" in h_body.lower(),
           f"body: {h_body!r}" if "ok" not in h_body.lower() else "")

    # 3c. App port 3000 must NOT be open on the host.
    app_open = port_open("localhost", APP_PORT)
    record(f"App port {APP_PORT} is NOT open on host", not app_open,
           f"Port {APP_PORT} is unexpectedly accessible from host!" if app_open else "")


def test_nginx_config_in_container() -> None:
    """Group 4 — Run nginx -t inside the proxy container."""
    print(_c(colours.BOLD, "\n── Group 4: Nginx Config Validation (in container) ─────"))

    if not docker_available():
        record("nginx -t passes inside proxy container", None,
               "Docker not available; skipping")
        return

    code, out, err = run([
        "docker", "exec", "demo-nginx-proxy",
        "nginx", "-t",
    ])
    combined = (out + err).strip()
    passed = code == 0 and "syntax is ok" in combined.lower()
    detail = ""
    if not passed:
        detail = combined.splitlines()[-1] if combined else f"exit {code}"
    record("nginx -t passes inside proxy container", passed, detail)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def print_summary() -> int:
    """Print final summary and return exit code (0 = all pass/skip, 1 = any fail)."""
    print(_c(colours.BOLD, "\n── Summary ──────────────────────────────────────────────"))
    passed  = sum(1 for r in results if r["status"] == "PASS")
    failed  = sum(1 for r in results if r["status"] == "FAIL")
    skipped = sum(1 for r in results if r["status"] == "SKIP")

    print(f"  Total : {len(results)}")
    print(f"  {_c(colours.GREEN, 'Passed')}: {passed}")
    print(f"  {_c(colours.RED,   'Failed')}: {failed}")
    print(f"  {_c(colours.YELLOW,'Skipped')}: {skipped}  (stack not running or tool not available)")
    print()

    if failed:
        print(_c(colours.RED, "  ✗ One or more tests FAILED."))
        return 1

    if skipped:
        print(_c(colours.YELLOW,
                 "  ⚠ Some tests were skipped because the stack is not running or\n"
                 "    a required tool is unavailable. Start the stack with:\n"
                 "      bash scripts/deploy.sh\n"
                 "    then re-run this test suite."))
        return 0

    print(_c(colours.GREEN, "  ✓ All tests passed."))
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    print(_c(colours.BOLD,
             "docker-nginx-deployment — Automated Deployment Tests"))
    print(f"  Project root : {PROJECT_ROOT}")
    print(f"  Nginx port   : {NGINX_PORT}")
    print(f"  Health wait  : {HEALTH_TIMEOUT}s")

    test_static_checks()
    test_docker_state()
    test_http()
    test_nginx_config_in_container()

    return print_summary()


if __name__ == "__main__":
    sys.exit(main())

