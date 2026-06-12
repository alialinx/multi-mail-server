import dns.resolver
import dns.reversename

from . import dkim
from .config import MAIL_HOSTNAME, SERVER_IP


def _txt(name):
    try:
        answers = dns.resolver.resolve(name, "TXT")
        return ["".join(part.decode() for part in r.strings) for r in answers]
    except Exception:
        return []


def _a(name):
    try:
        return [r.address for r in dns.resolver.resolve(name, "A")]
    except Exception:
        return []


def _mx(name):
    try:
        return [str(r.exchange).rstrip(".") for r in dns.resolver.resolve(name, "MX")]
    except Exception:
        return []


def _ptr(ip):
    try:
        rev = dns.reversename.from_address(ip)
        return [str(r).rstrip(".") for r in dns.resolver.resolve(rev, "PTR")]
    except Exception:
        return []


def _blacklisted(ip):
    reversed_ip = ".".join(reversed(ip.split(".")))
    try:
        dns.resolver.resolve(f"{reversed_ip}.zen.spamhaus.org", "A")
        return True
    except dns.resolver.NXDOMAIN:
        return False
    except Exception:
        return None


def result(name, ok, detail):
    return {"check": name, "ok": ok, "detail": detail}


def run(domain):
    mail_host = f"mail.{domain}"
    results = []

    a = _a(mail_host)
    results.append(result("A record", SERVER_IP in a, f"{mail_host} -> {a or 'none'}, expected {SERVER_IP}"))

    mx = _mx(domain)
    results.append(result("MX record", mail_host in mx, f"{domain} MX -> {mx or 'none'}, expected {mail_host}"))

    spf = _txt(domain)
    has_spf = any("v=spf1" in t for t in spf)
    results.append(result("SPF record", has_spf, "found" if has_spf else f"no v=spf1 TXT on {domain}"))

    dkim_name = f"default._domainkey.{domain}"
    published = " ".join(_txt(dkim_name))
    try:
        expected = dkim.record_for(domain).split("p=", 1)[1][:40]
        dkim_ok = expected in published.replace(" ", "")
    except Exception:
        dkim_ok = "v=DKIM1" in published
    results.append(result("DKIM record", dkim_ok, "found and matches" if dkim_ok else f"missing or wrong on {dkim_name}"))

    dmarc = _txt(f"_dmarc.{domain}")
    has_dmarc = any("v=DMARC1" in t for t in dmarc)
    results.append(result("DMARC record", has_dmarc, "found" if has_dmarc else f"no v=DMARC1 TXT on _dmarc.{domain}"))

    ptr = _ptr(SERVER_IP)
    confirms = any(SERVER_IP in _a(name) for name in ptr)
    detail = f"{SERVER_IP} PTR -> {ptr or 'none'}"
    if ptr and not confirms:
        detail += " (does not forward-confirm)"
    if ptr and MAIL_HOSTNAME not in ptr:
        detail += f" (does not match mail hostname {MAIL_HOSTNAME})"
    results.append(result("PTR reverse DNS", bool(ptr) and confirms, detail))

    listed = _blacklisted(SERVER_IP)
    if listed is None:
        results.append(result("Spamhaus blacklist", None, "could not check"))
    else:
        results.append(result("Spamhaus blacklist", not listed, "listed" if listed else "not listed"))

    return results
