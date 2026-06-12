# Install

## Requirements

- A Linux server with a public IP (a real VPS or bare metal, not Docker Desktop)
- A reverse DNS (PTR) record for your server IP, set at your hosting provider
- Outbound port 25 not blocked by your provider

Docker is installed automatically by `install.sh` if it is missing.

You open the firewall yourself; the installer does not touch it. Open: 25, 80, 143, 443, 465, 587, 993 to the internet, and the API port (default 8080) only to your own IP.

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
| Admin username | Login name for the API, default `admin`. | Used to log in to Swagger. |
| Admin password | Login password. It is typed hidden, so nothing shows on screen. That is normal. | Used to log in to Swagger. Save it somewhere. |

The installer also generates random secrets (database password, API key, JWT secret) and writes them to `.env`. You do not type these.

Then it builds the images, starts the database and API, creates the database tables and base config, and starts the rest of the stack. When it finishes it prints the Swagger UI address.

## Manage everything from Swagger

Open `http://<server>:<API_PORT>/docs`. Click **Authorize** and log in with your admin username and password.

Full endpoint list is in [API.md](API.md). The common flow:

1. `POST /domains` with `{ "name": "example.com" }`. The response has the DNS records to set.
2. Set the A and MX records, wait for them to propagate.
3. `POST /certs/issue/example.com` to get the TLS certificate.
4. Set the SPF, DKIM and DMARC records.
5. `POST /users` with `{ "email": "info@example.com", "password": "..." }`.

## Certificate renewal

Certificates do not renew on their own. Add a daily cron job on the host that calls the renew endpoint:

```
0 3 * * * curl -s -X POST -H "X-API-Key: YOUR_KEY" http://127.0.0.1:8080/certs/renew
```

## Notes

- Users and aliases are read live from the database. Adding or removing them does not restart any service.
- Adding or removing a domain regenerates config and reloads the mail services. See [ARCHITECTURE.md](ARCHITECTURE.md).
- Never commit `.env`, the `certs` volume, or DKIM keys.
- If you start the stack by hand instead of `install.sh`, run the one-time setup first: `docker compose exec api python -m mailctl.bootstrap`.
