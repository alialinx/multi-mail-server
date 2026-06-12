FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends spamassassin spamass-milter \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /var/lib/spamassassin

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8892
ENTRYPOINT ["/entrypoint.sh"]
