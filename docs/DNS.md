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

Set a PTR record for your server IP that points back to your mail hostname, for example `mx.example.com`. This is done at your hosting provider, not in your normal DNS zone. Many receivers reject mail from IPs without a matching PTR.

## Order

1. Set the A and MX records first.
2. Wait for them to propagate.
3. Call `POST /certs/issue/example.com` to get the certificate (HTTP-01 needs the A record to resolve).
4. Set SPF, DKIM, and DMARC.
