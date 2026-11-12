FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends unbound dns-root-data \
    && rm -rf /var/lib/apt/lists/*

EXPOSE 53/udp 53/tcp
ENTRYPOINT ["unbound", "-d", "-c", "/etc/unbound/unbound.conf"]
