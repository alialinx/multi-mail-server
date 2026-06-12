FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends fail2ban iptables \
    && rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["fail2ban-server", "-f", "-x", "-v"]
