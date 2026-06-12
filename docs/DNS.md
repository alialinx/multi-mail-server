# DNS

`POST /domains` returns the records for a domain, and `GET /domains/{name}/dns` returns them again. This page explains them.

Example for `example.com` with server IP `203.0.113.10`:


| Type | Name | Value |
|---|---|---|
| A | mail.example.com | 203.0.113.10 |
| A | autodiscover.example.com | 203.0.113.10 |
| MX | example.com | 10 mail.example.com |
| TXT | example.com | `v=spf1 mx -all` |
| TXT | default._domainkey.example.com | `v=DKIM1; k=rsa; p=...` |
| TXT | _dmarc.example.com | `v=DMARC1; p=none; rua=mailto:postmaster@example.com` |

## What each record does

- **A** points `mail.example.com` to your server. Clients connect here and TLS certificates are issued for this name.
- **MX** tells other mail servers to deliver mail for `example.com` to `mail.example.com`.
- **SPF** (the first TXT) says only your server may send mail for the domain.
- **DKIM** (the `default._domainkey` TXT) holds the public key. OpenDKIM signs with the private key and receivers check it with this record.
- **DMARC** (the `_dmarc` TXT) tells receivers what to do when SPF or DKIM fail. `p=none` only monitors. Move to `p=quarantine` or `p=reject` later.

## PTR (reverse DNS)

PTR maps your server IP back to a hostname. It is the opposite of an A record.

Important: **PTR belongs to the IP, not to a domain.** One server with one IP has exactly one PTR, no matter how many domains you host. Set it to your mail hostname, for example `mx.example.com`, which is the value you chose at install as `MAIL_HOSTNAME`. All your domains send out through this one IP and announce this one hostname (HELO), so one PTR covers all of them.

You set PTR at your hosting provider, not in your normal DNS zone, because the provider owns the IP block.

To make it forward-confirm, also add an A record `mx.example.com -> your IP`. The PTR hostname and its A record must point at each other.

### Risks and limits

- **You do not control it directly.** Only the IP owner (your hosting provider) can set PTR. If they refuse or are slow, big receivers like Gmail and Outlook may reject or spam-folder your mail.
- **One PTR per IP.** You cannot give each domain its own PTR on a single IP. All domains share the `mx.example.com` identity. This is normal and fine.
- **If you change `MAIL_HOSTNAME` later**, update the PTR and the A record together, or forward-confirm breaks.
- **If the hosting provider changes your IP**, the PTR breaks until you set it again.
- **No PTR or a mismatched PTR is one of the top reasons mail lands in spam.** Set it before you start sending.

Use `GET /domains/{name}/check` to verify the PTR and the other records are correct. See [API.md](API.md).

## Order

1. Set the A and MX records first.
2. Wait for them to propagate.
3. Call `POST /certs/issue/example.com` to get the certificate (HTTP-01 needs the A record to resolve).
4. Set SPF, DKIM, and DMARC.
