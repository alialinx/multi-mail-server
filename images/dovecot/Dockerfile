FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends dovecot-core dovecot-imapd dovecot-lmtp dovecot-pgsql dovecot-sieve dovecot-managesieved gettext-base \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -g 5000 vmail \
    && useradd -g vmail -u 5000 -d /home/mailservers -s /usr/sbin/nologin vmail

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 2143 2993 24 12345
ENTRYPOINT ["/entrypoint.sh"]
