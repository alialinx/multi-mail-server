#!/bin/sh
set -e

cp /etc/postfix/main.cf.tmpl /etc/postfix/main.cf

mkdir -p /etc/postfix/pgsql
for f in /etc/postfix/pgsql.tmpl/*.cf; do
    envsubst '${POSTGRES_PASSWORD}' < "$f" > "/etc/postfix/pgsql/$(basename "$f")"
done

postconf -e "myhostname=${MAIL_HOSTNAME}"

mkdir -p /var/log/mail
touch /var/log/mail/postfix.log

mkdir -p /gen-config/postfix
touch /gen-config/postfix/sni
postmap -F hash:/gen-config/postfix/sni

exec postfix start-fg
