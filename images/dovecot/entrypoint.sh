#!/bin/sh
set -e

envsubst '${POSTGRES_PASSWORD}' < /etc/dovecot/dovecot-sql.conf.ext.tmpl > /etc/dovecot/dovecot-sql.conf.ext
chmod 600 /etc/dovecot/dovecot-sql.conf.ext

mkdir -p /home/mailservers
chown vmail:vmail /home/mailservers

mkdir -p /var/sieve
chown -R vmail:vmail /var/sieve

mkdir -p /var/log/mail
touch /var/log/mail/dovecot.log

exec dovecot -F
