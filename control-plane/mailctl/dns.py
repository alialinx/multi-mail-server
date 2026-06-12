from .config import SERVER_IP


def records(domain, dkim_value):
    return [
        {"type": "A", "name": f"mail.{domain}", "value": SERVER_IP, "purpose": "Points your mail host to the server"},
        {"type": "MX", "name": domain, "value": f"10 mail.{domain}", "purpose": "Where other servers deliver mail for this domain"},
        {"type": "TXT", "name": domain, "value": "v=spf1 mx -all", "purpose": "SPF: only your server may send mail for this domain"},
        {"type": "TXT", "name": f"default._domainkey.{domain}", "value": dkim_value, "purpose": "DKIM: public key receivers use to verify your signature"},
        {"type": "TXT", "name": f"_dmarc.{domain}", "value": f"v=DMARC1; p=none; rua=mailto:postmaster@{domain}", "purpose": "DMARC: what receivers do if SPF or DKIM fail"},
    ]
