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
- Status: **mitigated**. Endpoints need auth: an admin login (username and password, returns a bearer token that lasts 8 hours) or a static `X-API-Key` for automation. Only `/health`, `/docs`, and `/token` are open. Credentials and the JWT secret are in `.env`.
- Also do: put the API port behind a firewall, and put it behind HTTPS in production so the login and tokens are not sent in clear text.

### Passwords in API requests
Passwords are sent in the body of `POST /users` and `PUT /users/{email}/password`.
- Status: **accepted**. Use HTTPS for the API and do not log request bodies. Passwords are stored hashed as SHA512-CRYPT.

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

## Not in Phase 1

Monitoring, alerting, mail queue management, log rotation, and fail2ban are not included yet.
- Status: **planned**.
