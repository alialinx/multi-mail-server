# Install

## Requirements

- A Linux server with a public IP (a real VPS or bare metal, not Docker Desktop)
- A reverse DNS (PTR) record for your server IP, set at your hosting provider
- Outbound port 25 not blocked by your provider

Docker is installed automatically by `install.sh` if it is missing.

You open the firewall yourself; the installer does not touch it. Open: 25, 80, 143, 443, 465, 587, 993 to the internet, and the web port (default 3000) and API port (default 8080) only to your own IP. If you serve the panel on your mail hostname (see below), keep 3000 and 8080 closed.

## Steps

```
git clone <repo-url> mail-platform
cd mail-platform
./install.sh
```

`install.sh` asks you a few things and saves them to `.env`. You press Enter after each answer.

| Question | What it is | Why it is needed |
|---|---|---|
| Server public IP | Your server's public IP. It is auto-detected, press Enter to accept. | It goes into the A and MX DNS records for your domains. |
| Mail hostname | One name for the server itself, like `mx.example.com`. Not one per domain. | The server announces this name when it sends mail (HELO) and your PTR points to it. See [DNS.md](DNS.md). |
| ACME email | Your email address. | Let's Encrypt uses it for certificate expiry notices. |
| API port | Port for the admin API, default 8080. Any port except 8000. | This is where you open the Swagger UI. |
| Web panel port | Port for the admin web panel, default 3000. | This is where you open the browser panel. |
| Admin username | Login name, default `admin`. | Used to log in to the web panel and Swagger. |
| Admin password | Login password. It is typed hidden, so nothing shows on screen. That is normal. | Used to log in to the web panel and Swagger. Save it somewhere. |

The installer also generates random secrets (database password, API key, JWT secret) and writes them to `.env`. You do not type these.

Then it builds the images, starts the database and API, creates the database tables and base config, and starts the rest of the stack. When it finishes it prints the Swagger UI address.

## Manage everything from the web panel

Open `http://<server>:<WEB_PORT>/` and log in with your admin username and password. From there you manage domains, users, aliases, quota, auto-reply and certificates. The panel is a static UI served by its own nginx container; it calls the same API, proxied at `/api/`, so only the web port needs to be reachable from your browser.

If you prefer raw REST, the Swagger UI is at `http://<server>:<API_PORT>/docs` (click **Authorize**, same credentials). Full endpoint list is in [API.md](API.md).

### Serve the panel on your mail hostname (HTTPS)

You can open the panel at `https://<MAIL_HOSTNAME>/` instead of `http://<server>:3000/`. Traefik serves it on port 443 with a Let's Encrypt certificate and lets in only the IPs you allow.

1. Make sure `MAIL_HOSTNAME` (for example `mx.example.com`) has an A record pointing to your server.
2. In `.env`, set the IPs or ranges that may open the panel, separated by commas. For example your VPN: `PANEL_ALLOW_IPS=10.8.0.0/24,203.0.113.7`
3. In `.env`, set `ADMIN_BIND=127.0.0.1`. Ports 3000 and 8080 then listen only inside the server, so the panel is reachable only through HTTPS.
4. Run `docker compose up -d --build api web`.
5. Get the certificate from inside the server: log in with `curl -X POST http://127.0.0.1:8080/token -d "username=admin&password=YOUR_PASS"`, then call `curl -X POST http://127.0.0.1:8080/certs/panel -H "Authorization: Bearer <token>"`.

Everyone else gets `403 Forbidden`. If `PANEL_ALLOW_IPS` is empty, the panel is not served on the hostname at all. The certificate renews with the others.

With `ADMIN_BIND=127.0.0.1` the Swagger UI is only reachable from the server itself, for example through an SSH tunnel: `ssh -L 8080:127.0.0.1:8080 <server>`, then open `http://localhost:8080/docs`.

The common flow:

1. `POST /domains` with `{ "name": "example.com" }`. The response has the DNS records to set.
2. Set the A and MX records, wait for them to propagate.
3. `POST /certs/issue/example.com` to get the TLS certificate.
4. Set the SPF, DKIM and DMARC records.
5. `POST /users` with `{ "email": "info@example.com", "password": "..." }`.

## Certificate renewal

Renewal is automatic. The API container runs a background task that renews
due certificates twice a day, so you do not need a cron job. You can see each
domain's expiry on the Dashboard, or force a renewal now with `POST /certs/renew`.

If you prefer to run it from the host instead, the command still works:

```
docker compose exec -T api python -m mailctl.renew
```

## Notes

- Users and aliases are read live from the database. Adding or removing them does not restart any service.
- Adding or removing a domain regenerates config and reloads the mail services. See [ARCHITECTURE.md](ARCHITECTURE.md).
- Never commit `.env`, the `certs` volume, or DKIM keys.
- If you start the stack by hand instead of `install.sh`, run the one-time setup first: `docker compose exec api python -m mailctl.bootstrap`.
