# API

The control plane also runs a REST API with a Swagger UI. The CLI and the API call the same code, so they do the same things.

## Where

The API runs in its own container on the port you set as `API_PORT` in `.env` (default 8080, not 8000).

- Swagger UI: `http://<server>:<API_PORT>/docs`
- Health check (open, no key): `http://<server>:<API_PORT>/health`

## Auth

You log in with an admin username and password. Everything except `/health`, `/docs`, and `/token` needs a valid login token.

You set the admin username and password during install (stored in `.env` as `ADMIN_USER` and `ADMIN_PASSWORD`). In Swagger, click **Authorize**, type the username and password, and you are logged in. Behind the scenes this calls `POST /token` and gets a bearer token that lasts 8 hours.

From the command line:

```
curl -X POST http://<server>:8080/token -d "username=admin&password=YOUR_PASS"
```

The response has `access_token`. Send it on later requests as `Authorization: Bearer <token>`.

## Endpoints

### Domains

| Method | Path | Body | Action |
|---|---|---|---|
| GET | /domains | - | list domains |
| POST | /domains | `{ "name": "example.com" }` | add domain, returns DNS records and cert status |
| GET | /domains/{name}/dns | - | DNS records again |
| GET | /domains/{name}/check | - | check deliverability: A, MX, SPF, DKIM, DMARC, PTR, blacklist |
| POST | /domains/{name}/enable | - | enable domain |
| POST | /domains/{name}/disable | - | disable domain |
| DELETE | /domains/{name} | - | remove domain |

### Users

| Method | Path | Body | Action |
|---|---|---|---|
| GET | /users?domain=example.com | - | list users |
| GET | /users/usage | - | map of email to mailbox storage used (MB) and percent of quota |
| POST | /users | `{ "email": "info@example.com", "password": "...", "quota_mb": 0 }` | add user |
| PUT | /users/{email}/password | `{ "password": "..." }` | change password |
| POST | /users/{email}/enable | - | enable user |
| POST | /users/{email}/disable | - | disable user |
| PUT | /users/{email}/quota | `{ "quota_mb": 1024 }` | set quota in MB, 0 is unlimited |
| PUT | /users/{email}/autoreply | `{ "active": true, "subject": "...", "text": "..." }` | set vacation auto-reply |
| DELETE | /users/{email} | - | remove user |

### Aliases (forwarding)

| Method | Path | Body | Action |
|---|---|---|---|
| GET | /aliases | - | list aliases |
| POST | /aliases | `{ "address": "info@example.com", "goto": "user@example.org", "keep_copy": false }` | add forwarding |
| DELETE | /aliases?address=info@example.com&goto=user@example.org | - | remove (goto is optional) |

For a domain catch-all, use an address like `@example.com`. With `keep_copy: true` and a real mailbox address, a copy stays in the mailbox and the mail is also forwarded.

### Certificates

| Method | Path | Action |
|---|---|---|
| POST | /certs/issue/{domain} | issue certificate |
| POST | /certs/renew | renew all certificates now |

Renewal also runs automatically in the background twice a day, so you rarely need `POST /certs/renew`.

### Status and mail queue

| Method | Path | Action |
|---|---|---|
| GET | /status | dashboard data: domain/user/alias counts, service health, disk usage, mail queue size, per-domain certificate expiry |
| GET | /stats | live CPU and memory usage per container plus host totals (from `docker stats`) |
| GET | /mailstats?days=30&domain= | daily sent/received/bounced counts per day; optional `domain` filter |
| WS | /ws/logs?source=postfix&token=&noise=0 | WebSocket that streams new log lines live (`tail -f`); token is the bearer token as a query param |
| GET | /queue | list queued messages (id, sender, recipients, queue, delay reason) |
| POST | /queue/flush | retry delivery of the whole queue now |
| DELETE | /queue/{id} | delete one message; use `ALL` to delete the whole queue |

### Logs and security

| Method | Path | Action |
|---|---|---|
| GET | /logs?source=postfix&q=&limit=200 | recent log lines from `postfix` or `dovecot`; `q` filters (grep), trace a mail by recipient or message-id |
| GET | /fail2ban | jails and their currently banned IPs |
| DELETE | /fail2ban/banned/{ip} | unban an IP |

## Deliverability check

`GET /domains/{name}/check` looks up live DNS and tells you if the domain is set up to avoid the spam folder. Each item is `ok: true`, `ok: false`, or `ok: null` (could not check). It checks:

- A record: `mail.<domain>` points to the server IP
- MX record: the domain points to `mail.<domain>`
- SPF, DKIM, DMARC TXT records exist and the DKIM key matches
- PTR: the server IP has reverse DNS that forward-confirms
- Spamhaus: the server IP is not on the zen blocklist

Run this after setting DNS to find what is missing before you send real mail.

## Notes

- Some calls take time. `POST /domains` generates a DKIM key, reconciles config, and tries to get a certificate, so it may take several seconds.
- The API container has access to the Docker socket, like the control plane. Protect the API port with a firewall and keep the API key secret. See [RISKS.md](RISKS.md).
