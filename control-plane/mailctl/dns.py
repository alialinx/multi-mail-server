from .config import SERVER_IP


def records(domain, dkim_value):
    lines = [
        f"A      mail.{domain}                  {SERVER_IP}",
        f"A      autodiscover.{domain}          {SERVER_IP}",
        f"MX     {domain}                       10 mail.{domain}",
        f'TXT    {domain}                       "v=spf1 mx -all"',
        f'TXT    default._domainkey.{domain}    "{dkim_value}"',
        f'TXT    _dmarc.{domain}                "v=DMARC1; p=none; rua=mailto:postmaster@{domain}"',
    ]
    return "\n".join(lines)
