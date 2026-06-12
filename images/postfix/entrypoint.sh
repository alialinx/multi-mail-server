#!/bin/sh
set -e

cp /etc/postfix/main.cf.tmpl /etc/postfix/main.cf

mkdir -p /etc/postfix/pgsql
for f in /etc/postfix/pgsql.tmpl/*.cf; do
    envsubst '${POSTGRES_PASSWORD}' < "$f" > "/etc/postfix/pgsql/$(basename "$f")"
done

clean_hostname=$(printf '%s' "${MAIL_HOSTNAME}" | tr -cd 'a-zA-Z0-9.-')
postconf -e "myhostname=${clean_hostname}"

mkdir -p /var/log/mail
touch /var/log/mail/postfix.log

mkdir -p /gen-config/postfix
touch /gen-config/postfix/sni
postmap -F hash:/gen-config/postfix/sni

exec postfix start-fg
