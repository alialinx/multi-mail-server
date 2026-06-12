#!/bin/sh
set -e

/usr/sbin/spamd -d --pidfile=/var/run/spamd.pid --max-children=3 --helper-home-dir=/var/lib/spamassassin

exec /usr/sbin/spamass-milter -p inet:8892@0.0.0.0
