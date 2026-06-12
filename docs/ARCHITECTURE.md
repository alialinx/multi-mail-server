# Architecture

## Idea

PostgreSQL is the single source of truth. Everything else is generated from it.

You manage the system from a REST API with a Swagger UI. There is no separate admin command; the API is the single interface.

There are two kinds of changes:

1. Users and aliases. Postfix and Dovecot read these live from the database with SQL queries. Adding or removing them needs no reload.
2. Domains. A domain needs a TLS certificate, a DKIM key, and entries in several config files. When a domain changes, the API regenerates those files and reloads the services. This is called reconcile.

## Services

Each part runs in its own container. They are wired with one Docker network called `mailnet`.

| Service | Job |
|---|---|
| postgres | The database `mailservers` with tables `domains`, `users`, `aliases` |
| postfix | SMTP. Receives mail on 25, sends mail, submission on 465 and 587 |
| dovecot | IMAP on 143 and 993, and LMTP for local delivery |
| opendkim | Signs outgoing mail with DKIM |
| spamassassin | Scans incoming mail and marks spam |
| haproxy | The edge for mail ports. Terminates TLS for 465 and 993 |
| traefik | The edge for web ports 80 and 443 |
| acme-web | A tiny nginx that serves Let's Encrypt HTTP challenges |
| certbot | Gets and renews all certificates |
| fail2ban | Bans IPs that brute-force SMTP or IMAP login |
| api | The REST API, the reconcile logic, and the bootstrap step. This is the control plane |

## Ports and client IP

HAProxy runs with host networking so it sees the real client IP. This matters for postscreen, DNS blocklists, and rate limits.

Postfix and Dovecot run on the `mailnet` bridge. HAProxy connects to them on `127.0.0.1` (they publish their internal ports there) and forwards the connection with the PROXY protocol, so the real client IP is preserved.

Port flow:

| Public port | HAProxy action | Backend |
|---|---|---|
| 25 | pass through with PROXY protocol | postfix postscreen on 2525 |
| 465 | terminate TLS, then PROXY protocol | postfix on 2465 |
| 587 | pass through with PROXY protocol | postfix on 2587 |
| 143 | pass through with PROXY protocol | dovecot on 2143 |
| 993 | terminate TLS, then PROXY protocol | dovecot on 2993 |

## Reconcile

The API reads the active domains and writes these files into the shared `gen-config` volume:

| File | Used by |
|---|---|
| `postfix/sni` | Postfix per-domain TLS via `tls_server_sni_maps` |
| `dovecot/sni.conf` | Dovecot per-domain TLS via `local_name` blocks |
| `haproxy/mail-465.crtlist`, `haproxy/mail-993.crtlist` | HAProxy SNI certificates |
| `opendkim/key.table`, `signing.table`, `trusted.hosts` | OpenDKIM signing |
| `traefik/dynamic.yml` | Traefik routers and certificates |
| `certs/*.pem` | Combined cert and key files for HAProxy |

After writing, it reloads opendkim, postfix, dovecot, and haproxy. Traefik picks up its file on its own.

## Certificates

One certbot container gets all certificates with the HTTP-01 challenge. Traefik routes the challenge path to the `acme-web` nginx, which serves the challenge files. Certbot writes certificates to the shared `certs` volume under `/certs/live/mail.<domain>/`. HAProxy, Dovecot, Postfix, and Traefik all read from there.

There is one self-signed default certificate at `/certs/default`. It is the fallback when a connection does not match any domain.

## Spam filtering and bans

Incoming mail goes through SpamAssassin as a Postfix milter. It adds an `X-Spam-Flag` header. A global Sieve rule (`spam.sieve`) moves flagged mail into the Junk folder. Submission ports (465, 587) skip SpamAssassin so your own users' outgoing mail is not scanned.

Fail2ban reads the Postfix and Dovecot log files from the shared `maillog` volume and bans IPs that fail login too many times. It runs on the host network with `NET_ADMIN` so it can add firewall rules for the public mail ports. Because HAProxy forwards the real client IP with the PROXY protocol, the logs show the real IP and the bans are correct.

## Reloads and the Docker socket

The API reloads other containers by running `docker exec` and `docker restart`. For this it mounts the host Docker socket. Keep the host secure, because access to the Docker socket is root-level access.

## Per-mailbox features

- Quota: Dovecot quota plugin. The per-user limit comes from the `quota` column and is passed to Dovecot in the user query.
- Auto-reply: Dovecot Sieve. The API writes a per-user vacation script to the shared `sievedata` volume at `/var/sieve/<domain>/<user>.sieve`. Dovecot runs it at delivery time.
- Forwarding: rows in the `aliases` table. Multiple rows for one address deliver to all targets, so "keep a copy and forward" is two rows. An address like `@example.com` is a catch-all.

## Data that must persist

These Docker volumes hold real data and must be backed up:

- `pgdata` the database
- `maildata` all mailboxes (`/home/mailservers/<domain>/<user>/Maildir`)
- `sievedata` per-user auto-reply scripts
- `certs` certificates
- `dkim-keys` DKIM private keys
