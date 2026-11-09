# Application container Dockerfile
#
# Serves the static site using Nginx on port 3000.
# This container is intentionally NOT exposed to the host.
# It is only reachable from the reverse-proxy container over the
# internal Docker network (app-net).
#
# Base image: nginx:1.27-alpine — small, stable, actively maintained.

FROM nginx:1.27-alpine

# Remove default Nginx config and content.
RUN rm -rf /usr/share/nginx/html/* \
    && rm /etc/nginx/conf.d/default.conf

# Copy application source files.
COPY index.html /usr/share/nginx/html/
COPY assets/   /usr/share/nginx/html/assets/

# Minimal Nginx config: serve static files on port 3000.
# No SSL, no gzip, no extra modules — keep it simple.
COPY nginx-app.conf /etc/nginx/conf.d/app.conf

EXPOSE 3000

# Health check: use 127.0.0.1 (not localhost) because on Alpine Linux,
# localhost may resolve to ::1 (IPv6) while Nginx only listens on IPv4.
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1:3000/ > /dev/null || exit 1

CMD ["nginx", "-g", "daemon off;"]
