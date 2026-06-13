import os
import shutil
import subprocess
from datetime import datetime, timezone

from cryptography import x509

from .config import CERTS_DIR
from .db import Alias, Domain, SessionLocal, User

EXPECTED_SERVICES = [
    "postgres", "postfix", "dovecot", "opendkim", "haproxy",
    "traefik", "acme-web", "certbot", "fail2ban", "api", "web",
]


def _services():
    result = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}"],
        capture_output=True, text=True,
    )
    running = {}
    for line in result.stdout.splitlines():
        if "\t" in line:
            name, status = line.split("\t", 1)
            running[name] = status
    return [{"name": n, "up": n in running, "status": running.get(n, "down")} for n in EXPECTED_SERVICES]


def _queue_count():
    result = subprocess.run(
        ["docker", "exec", "postfix", "postqueue", "-j"],
        capture_output=True, text=True,
    )
    return sum(1 for line in result.stdout.splitlines() if line.strip())


def _cert_not_after(cert):
    try:
        return cert.not_valid_after_utc
    except AttributeError:
        return cert.not_valid_after.replace(tzinfo=timezone.utc)


def _certs():
    session = SessionLocal()
    try:
        domains = [d.name for d in session.query(Domain).order_by(Domain.name).all()]
    finally:
        session.close()

    out = []
    for name in domains:
        path = f"{CERTS_DIR}/live/mail.{name}/fullchain.pem"
        item = {"domain": name, "valid": False, "expires": None, "days_left": None}
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    cert = x509.load_pem_x509_certificate(f.read())
                expires = _cert_not_after(cert)
                days = (expires - datetime.now(timezone.utc)).days
                item.update(valid=days > 0, expires=expires.date().isoformat(), days_left=days)
            except Exception:
                pass
        out.append(item)
    return out


def get_status():
    session = SessionLocal()
    try:
        total = session.query(Domain).count()
        active = session.query(Domain).filter_by(active=True).count()
        users = session.query(User).count()
        aliases = session.query(Alias).count()
    finally:
        session.close()

    disk = shutil.disk_usage(CERTS_DIR)
    return {
        "domains": {"total": total, "active": active},
        "users": users,
        "aliases": aliases,
        "queue": {"count": _queue_count()},
        "disk": {
            "used": disk.used,
            "total": disk.total,
            "free": disk.free,
            "percent": round(disk.used / disk.total * 100, 1),
        },
        "services": _services(),
        "certs": _certs(),
    }
