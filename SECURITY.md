# Security Policy

## Scope

This document covers the `docker-nginx-deployment` portfolio project.

## Reporting a Vulnerability

This is a demonstration project, not a production service. If you find a
security issue in the code or configuration that could mislead developers
who copy this pattern, please open a GitHub Issue describing the problem.

## Known Limitations

| Area | Limitation |
|------|-----------|
| **HTTP only** | The project does not configure HTTPS. TLS termination should be added before exposing this pattern to the public internet. See [Future Improvements](#future-improvements) in the README. |
| **No authentication** | The demo application and the `/healthz` endpoint are unauthenticated. This is intentional for a demo, but authentication should be added in production use. |
| **Static content only** | The application serves static HTML/CSS/JS. No dynamic input processing or user-supplied data is handled, so injection risks are minimal but not absent. |
| **Health endpoint** | `/healthz` is served directly by Nginx and reports only that the proxy container is running. It does not indicate database connectivity or external service health. |
| **Image pinning** | Base images are pinned to `nginx:1.27-alpine`. Review for updated versions periodically. |
| **Resource limits** | No CPU or memory limits are set in Compose. Add them in a real deployment. |
| **Logging** | Logs go to Docker's default `json-file` driver with size rotation. For production, forward logs to a centralised log aggregator. |
| **No rate limiting** | Nginx does not apply request-rate limiting in this demo. Add `limit_req_zone` for public-facing deployments. |

## Security Measures Implemented

- The application container does not publish any port to the host. All traffic
  enters through the Nginx reverse proxy.
- Both containers drop all Linux capabilities except those explicitly required
  (`NET_BIND_SERVICE`, `CHOWN`, `SETGID`, `SETUID`).
- No privileged mode or host networking is used.
- The `.env` file is excluded from Git via `.gitignore`.
- No secrets, API keys, or credentials are stored in this repository.
- Base images are pinned to specific major/minor versions, not `latest`.
- Log rotation is configured to prevent unbounded disk growth.

## Future Improvements

- TLS termination (Let's Encrypt or manual certificate) with HTTPS redirect.
- Nginx rate limiting (`limit_req_zone`).
- Read-only container filesystems where feasible.
- Docker resource limits (`mem_limit`, `cpus`).
- Centralised log aggregation (Loki, ELK, CloudWatch).
- Secrets management (Docker secrets or external vault).

