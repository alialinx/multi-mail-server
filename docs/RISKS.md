# Risks

This page lists known risks of the system, what is done about them now, and what is planned. Status meaning:

- **mitigated** - handled now
- **accepted** - known and acceptable for Phase 1
- **planned** - to be fixed in a later phase

## Security

### Docker socket on the control plane
The control plane mounts the host Docker socket so it can reload other containers. This is root-level access to the host. If the control plane is compromised, the host is compromised.
- Status: **accepted**
- Planned: replace `docker exec` reloads with a small per-service reload helper, or a restricted socket proxy.

### Config validation before reload
A broken generated config could take down a service or all domains at once.
- Status: **mitigated**. Before reloading, the control plane runs `postfix check`, `haproxy -c`, and `doveconf`. If any fails, nothing is reloaded and the command reports the error.

### Input validation
Domain and email values go into generated config files.
- Status: **mitigated**. The API checks domain and email format before writing anything. SQL is parameterized by SQLAlchemy.

### DKIM private key file mode
DKIM private keys are written with mode 0644 inside the keys volume.
- Status: **accepted** (stays inside the container and volume).
- Planned: tighten to 0640 with a shared group between control plane and opendkim.

### API exposes control over a network port
The REST API can do everything, including operations that use the Docker socket. It is reachable on `API_PORT`.
- Status: **mitigated**. Endpoints need an admin login (username and password, returns a bearer token that lasts 8 hours). Only `/health`, `/docs`, and `/token` are open. Credentials and the JWT secret are in `.env`. Certificate renewal runs inside the container (`python -m mailctl.renew`), so automation does not need an API key.
- Also do: put the API port behind a firewall, and put it behind HTTPS in production so the login and tokens are not sent in clear text.

### Passwords in API requests
Passwords are sent in the body of `POST /users` and `PUT /users/{email}/password`.
- Status: **accepted**. Use HTTPS for the API and do not log request bodies. Passwords are stored hashed as SHA512-CRYPT.

### Web panel exposes the same control as the API
The web panel (default port 3000) reverse-proxies `/api/` to the control plane, so anyone who can reach it and log in can do everything the API can.
- Status: **mitigated**. The panel ships no credentials; it stores only the bearer token the user gets after logging in with the admin username and password. The token is held in the browser and expires after 8 hours.
- Also do: serve the panel on your mail hostname with `PANEL_ALLOW_IPS` and `ADMIN_BIND=127.0.0.1` (see [INSTALL.md](INSTALL.md)). Then it is HTTPS only, open only to the IPs you allow, and ports 3000 and 8080 are closed. If you keep the web port, open it only to your own IP in the firewall.
- Note: the panel login has no attempt limit. The IP allow list is what stops password guessing, so do not leave the panel open to everyone.

## Availability and operations

### Single server, no high availability
If the server dies, all domains go down. There is no replication.
- Status: **accepted**.

### HAProxy restart drops connections
Adding or removing a domain, and renewing certificates, restarts HAProxy. Active IMAP and SMTP sessions are cut for a moment.
- Status: **accepted** for small and medium domain counts.
- Planned: switch HAProxy to a graceful reload instead of a full restart.

### Reconcile regenerates everything each time
Every domain change rewrites all generated config and restarts HAProxy and OpenDKIM. This is fine for tens of domains but gets heavy at hundreds.
- Status: **accepted**.
- Planned: update only what changed and use graceful reloads.

### Backups are manual
The volumes `pgdata`, `maildata`, `certs`, and `dkim-keys` hold all real data. Losing `dkim-keys` means re-publishing DKIM DNS records for every domain.
- Status: **accepted**. You must back these up yourself.
- Planned: a backup command.

## Certificates and DNS

### Let's Encrypt rate limits
Adding many domains quickly, or retrying a failed issue, can hit Let's Encrypt limits.
- Status: **accepted**. Use the staging ACME server (`ACME_SERVER` in `.env`) for testing.

### Certificate timing
HTTP-01 needs the `mail.<domain>` A record to resolve to the server. On a fresh domain the A record is not set yet, so `POST /domains` skips the certificate step and you call `POST /certs/issue/<domain>` after DNS propagates.
- Status: **mitigated** (the flow handles this and tells you what to do).

## Deliverability (not a code issue)

### IP reputation, PTR, blocklists, warm-up
Self-hosted mail can land in spam until the IP has a good reputation, a correct PTR record, and is not on blocklists.
- Status: **accepted**. This is an operational task, not something the code can fix.

### Port 25 may be blocked
Many providers block outbound port 25, which stops sending.
- Status: **accepted**. Ask your provider to open it.

### Fail2ban needs host firewall access
Fail2ban runs on the host network with `NET_ADMIN` and `NET_RAW` so it can add firewall rules. This is a privileged container that changes the host firewall.
- Status: **accepted**. It uses `iptables-allports`, so a banned IP is blocked on every host port, SSH too. Ports that Docker publishes (80, 443, and 3000/8080 if open) skip these rules, so a banned user can still open the panel. This looks like "mail and SSH are down but the web works". On some hosts its rules can interact with Docker's own iptables rules, so verify bans work after install.
- Also do: add your own IPs, your VPN and your app servers to `ignoreip` in `config/fail2ban/jail.local`, for example `ignoreip = 127.0.0.1/8 ::1 203.0.113.7 10.8.0.0/24`, then run `docker restart fail2ban`. The Postfix jail runs in `aggressive` mode, so a mail client with a wrong setting, or a test that drops the connection after STARTTLS, can ban you within minutes. To unban, use the panel or `DELETE /fail2ban/banned/{ip}`.

### Spamhaus free use has limits
Postscreen checks every incoming connection against Spamhaus zen and SpamCop through the local `unbound` resolver.
- Status: **accepted**. Spamhaus is free only for low volume, non-commercial use (roughly under 100k SMTP connections a day). If you host mail commercially or above that, get a Spamhaus Data Query Service (DQS) key and switch `postscreen_dnsbl_sites` to the DQS zone.
- Note: before the local resolver was added, Postfix asked 8.8.8.8, Spamhaus did not answer, and only SpamCop was really working.

### SpamAssassin is not enabled yet
The Debian package used did not ship a standalone `spamd` binary, so SpamAssassin is currently not wired in.
- Status: **planned**. Inbound spam is still reduced by postscreen and the DNS blocklists (Spamhaus, Spamcop) at SMTP time.
- Planned: add SpamAssassin back with a working `spamd`, then Bayes training and scheduled `sa-update`.

## Not in Phase 1

A status dashboard (service health, disk, queue size, certificate expiry) and
mail queue management (view, flush, delete) are now included, and certificate
renewal runs automatically. Alerting and log rotation are still planned.
- Status: **planned** (alerting, log rotation).
