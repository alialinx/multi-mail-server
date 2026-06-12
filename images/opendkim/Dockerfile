FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends opendkim opendkim-tools \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /var/run/opendkim && chown opendkim:opendkim /var/run/opendkim

EXPOSE 8891
ENTRYPOINT ["opendkim", "-f", "-x", "/etc/opendkim/opendkim.conf"]
