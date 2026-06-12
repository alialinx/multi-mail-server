# Mail Platform

Self-hosted multi-domain mail server. Docker-first. You add domains, users and aliases with one command. No manual editing of Postfix, Dovecot or OpenDKIM config.

Built on Postfix, Dovecot, PostgreSQL, OpenDKIM, HAProxy, Traefik and Let's Encrypt.

## What you get

- Multi-domain mail hosting on a single server
- SMTP (25, 465, 587) and IMAP (143, 993)
- DKIM signing per domain
- Automatic TLS certificates
- One PostgreSQL database as the single source of truth
- A REST API with a Swagger UI for all administration

## Requirements

- A Linux server (a real VPS or bare metal, not Docker Desktop) with a public IP
- A domain you control
- Outbound port 25 not blocked by your provider

Docker is installed automatically by `install.sh` if it is missing. You do not need to install it first.

### Open these ports in your firewall

The installer does not change your firewall. Open these yourself:

| Port | For |
|---|---|
| 25, 465, 587 | SMTP (receive and send) |
| 143, 993 | IMAP |
| 80, 443 | HTTP and HTTPS (certificates, web) |
| API port (default 8080) | admin API, open only to your own IP |

## Quick start

```
git clone <repo-url> mail-platform
cd mail-platform
./install.sh
```

When it finishes it prints the Swagger UI address, for example `http://<server>:8080/docs`. You manage everything from there: domains, users, aliases, forwarding, quota, auto-reply and certificates. The API key is in `.env`.

Add a domain with `POST /domains`, set the DNS records it returns, then add a user with `POST /users`.

## Documentation

- [docs/INSTALL.md](docs/INSTALL.md) - install and first run
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - how the parts fit together
- [docs/API.md](docs/API.md) - REST API and Swagger UI
- [docs/DNS.md](docs/DNS.md) - DNS records you need
- [docs/RISKS.md](docs/RISKS.md) - known risks and their status

## Status

Phase 1. REST API with Swagger and the full mail stack work. A web panel comes later.
