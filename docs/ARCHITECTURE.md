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
| haproxy | The edge for mail ports. Terminates TLS for 465 and 993 |
| traefik | The edge for web ports 80 and 443. Can also serve the web panel on `MAIL_HOSTNAME` for allowed IPs only |
| acme-web | A tiny nginx that serves Let's Encrypt HTTP challenges |
| certbot | Gets and renews all certificates |
| fail2ban | Bans IPs that brute-force SMTP or IMAP login |
| ratelimit | A small Postfix policy service that limits how many recipients each logged-in account can send to per hour |
| unbound | A small local DNS resolver for Postfix. Postscreen asks Spamhaus and SpamCop through it, because Spamhaus does not answer queries from big public resolvers like 8.8.8.8. If it is down, Postfix falls back to 8.8.8.8 and mail keeps flowing, only without Spamhaus |
| api | The REST API, the reconcile logic, and the bootstrap step. This is the control plane |
| web | A static admin panel (nginx) that calls the API. Serves the UI and reverse-proxies `/api/` to the api container |

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
| `traefik/dynamic.yml` | Traefik routers and certificates, plus the panel router, IP allow list and security headers when `PANEL_ALLOW_IPS` is set and the `MAIL_HOSTNAME` certificate exists |
| `certs/*.pem` | Combined cert and key files for HAProxy |

After writing, it reloads opendkim, postfix, dovecot, and haproxy. Traefik picks up its file on its own.

## Certificates

One certbot container gets all certificates with the HTTP-01 challenge. Traefik routes the challenge path to the `acme-web` nginx, which serves the challenge files. Certbot writes certificates to the shared `certs` volume under `/certs/live/mail.<domain>/`. The panel certificate goes to `/certs/live/<MAIL_HOSTNAME>/` and renews with the rest. HAProxy, Dovecot, Postfix, and Traefik all read from there.

There is one self-signed default certificate at `/certs/default`. It is the fallback when a connection does not match any domain.

## Spam filtering and bans

Inbound spam is reduced at SMTP time by postscreen and the DNS blocklists (Spamhaus, Spamcop) in the Postfix config. A global Sieve rule (`spam.sieve`) is ready to move mail marked with `X-Spam-Flag` into the Junk folder; the SpamAssassin scanner that sets that header is planned (see [RISKS.md](RISKS.md)).

Fail2ban reads the Postfix and Dovecot log files from the shared `maillog` volume and bans IPs that fail login too many times. It runs on the host network with `NET_ADMIN` so it can add firewall rules for the public mail ports. Because HAProxy forwards the real client IP with the PROXY protocol, the logs show the real IP and the bans are correct.

## Mail queue

Mail that cannot be delivered stays in the Postfix queue and is retried: first after 5 minutes, then with longer gaps up to about an hour. After 2 days (`maximal_queue_lifetime`) Postfix gives up and sends a bounce to the sender. Bounces themselves are retried for 1 day (`bounce_queue_lifetime`). The Postfix default is 5 days for both. It is shorter here because most mail is app notifications, and retrying the same dead or full mailbox for days hurts sender reputation.

## Sending limits

Each logged-in (SASL) account may send to a limited number of recipients per rolling hour: 250 by default, 2000 for addresses that start with `noreply@`. Set them with `RATE_LIMIT_PER_HOUR` and `RATE_LIMIT_NOREPLY_PER_HOUR` in `.env`. This stops a hacked password from sending thousands of spam mails and ruining the server IP.

Postfix asks the `ratelimit` container at the end of every message. Over the limit, the message gets `450 4.7.1 Sending limit reached`, a temporary error, so a normal mail client tries again later. Mail coming in from other servers is not counted. If the container is down, Postfix sends mail without limits instead of stopping. Limit hits show in `docker logs ratelimit` as `LIMIT <account>` lines.

The **Sending** page in the panel shows each account's numbers and lets you set a custom limit per account. Custom limits are stored in the `send_limits` table. The API writes them to `/gen-config/ratelimit/limits.json`, and the ratelimit service reads that file again whenever it changes, so no restart is needed.

The ratelimit service keeps hourly counts for 7 days and saves them every minute to the `ratelimit-data` volume, so a restart keeps the history. It serves the numbers on port 10041 (`GET /usage`), only inside the Docker network. The **Messages** button reads the Postfix log to list what an account sent recently.

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
