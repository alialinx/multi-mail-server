FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends postfix postfix-pgsql gettext-base \
    && rm -rf /var/lib/apt/lists/*

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 2525 2465 2587
ENTRYPOINT ["/entrypoint.sh"]
