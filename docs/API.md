# API

The control plane also runs a REST API with a Swagger UI. The CLI and the API call the same code, so they do the same things.

## Where

The API runs in its own container on the port you set as `API_PORT` in `.env` (default 8080, not 8000).

- Swagger UI: `http://<server>:<API_PORT>/docs`
- Health check (open, no key): `http://<server>:<API_PORT>/health`

## Auth

There are two ways to authenticate. Everything except `/health`, `/docs`, and `/token` needs auth.

### Login (for people, in Swagger)

You set an admin username and password during install (stored in `.env` as `ADMIN_USER` and `ADMIN_PASSWORD`). In Swagger, click **Authorize**, type the username and password, and you are logged in. Behind the scenes this calls `POST /token` and gets a bearer token that lasts 8 hours.

From the command line:

```
curl -X POST http://<server>:8080/token -d "username=admin&password=YOUR_PASS"
```

The response has `access_token`. Send it as `Authorization: Bearer <token>`.

### API key (for scripts and cron)

A static key is also generated during install and stored in `.env` as `API_KEY`. Send it in the `X-API-Key` header. This is handy for automation like certificate renewal.

```
curl -H "X-API-Key: $API_KEY" http://<server>:8080/domains
```

A request is accepted if it has a valid login token **or** the correct API key.

## Endpoints

### Domains

| Method | Path | Body | Action |
|---|---|---|---|
| GET | /domains | - | list domains |
| POST | /domains | `{ "name": "example.com" }` | add domain, returns DNS records and cert status |
| GET | /domains/{name}/dns | - | DNS records again |
| POST | /domains/{name}/enable | - | enable domain |
| POST | /domains/{name}/disable | - | disable domain |
| DELETE | /domains/{name} | - | remove domain |

### Users

| Method | Path | Body | Action |
|---|---|---|---|
| GET | /users?domain=example.com | - | list users |
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
| POST | /certs/renew | renew all certificates |

## Notes

- Some calls take time. `POST /domains` generates a DKIM key, reconciles config, and tries to get a certificate, so it may take several seconds.
- The API container has access to the Docker socket, like the control plane. Protect the API port with a firewall and keep the API key secret. See [RISKS.md](RISKS.md).
