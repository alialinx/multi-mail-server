import dns.resolver
import dns.reversename

from . import dkim
from .config import MAIL_HOSTNAME, SERVER_IP

_public = dns.resolver.Resolver(configure=False)
_public.nameservers = ["8.8.8.8", "1.1.1.1"]
_public.timeout = 5
_public.lifetime = 5


def _txt(name):
    try:
        answers = _public.resolve(name, "TXT")
        return ["".join(part.decode() for part in r.strings) for r in answers]
    except Exception:
        return []


def _a(name):
    try:
        return [r.address for r in _public.resolve(name, "A")]
    except Exception:
        return []


def _mx(name):
    try:
        return [str(r.exchange).rstrip(".") for r in _public.resolve(name, "MX")]
    except Exception:
        return []


def _ptr(ip):
    try:
        rev = dns.reversename.from_address(ip)
        return [str(r).rstrip(".") for r in _public.resolve(rev, "PTR")]
    except Exception:
        return []


BLOCKLISTS = [
    ("Spamhaus blacklist", "zen.spamhaus.org"),
    ("Barracuda blacklist", "b.barracudacentral.org"),
    ("SpamCop blacklist", "bl.spamcop.net"),
]


def _zone_resolver(zone):
    ips = []
    try:
        for ns in _public.resolve(zone, "NS"):
            ips += _a(str(ns.target))
    except Exception:
        pass
    if not ips:
        return _public
    resolver = dns.resolver.Resolver(configure=False)
    resolver.nameservers = ips
    resolver.timeout = 5
    resolver.lifetime = 5
    return resolver


def _lookup(resolver, name):
    try:
        return [r.address for r in resolver.resolve(name, "A")]
    except dns.resolver.NXDOMAIN:
        return []
    except Exception:
        return None


def _blacklisted(ip, zone):
    resolver = _zone_resolver(zone)
    test = _lookup(resolver, f"2.0.0.127.{zone}")
    if not test or any(a.startswith("127.255.255.") for a in test):
        return None
    reversed_ip = ".".join(reversed(ip.split(".")))
    answers = _lookup(resolver, f"{reversed_ip}.{zone}")
    if answers is None or any(a.startswith("127.255.255.") for a in answers):
        return None
    return len(answers) > 0


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

    for name, zone in BLOCKLISTS:
        listed = _blacklisted(SERVER_IP, zone)
        if listed is None:
            results.append(result(name, None, f"could not check {zone}"))
        else:
            results.append(result(name, not listed, f"{SERVER_IP} listed on {zone}" if listed else "not listed"))

    return results
