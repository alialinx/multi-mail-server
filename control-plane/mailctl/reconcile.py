import os
import subprocess

from jinja2 import Environment, FileSystemLoader

from . import reload as reload_services
from .config import CERTS_DIR, GEN_CONFIG_DIR, MAIL_HOSTNAME, PANEL_ALLOW_IPS
from .db import Domain, SessionLocal

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))


def cert_dir(name):
    return f"{CERTS_DIR}/live/mail.{name}"


def has_cert(name):
    return has_host_cert(f"mail.{name}")


def has_host_cert(hostname):
    d = f"{CERTS_DIR}/live/{hostname}"
    return os.path.exists(f"{d}/fullchain.pem") and os.path.exists(f"{d}/privkey.pem")


def panel_host():
    if PANEL_ALLOW_IPS and has_host_cert(MAIL_HOSTNAME):
        return MAIL_HOSTNAME
    return None


def read(path):
    with open(path) as f:
        return f.read()


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


def render(template, **ctx):
    return env.get_template(template).render(**ctx)


def ensure_default_cert():
    d = f"{CERTS_DIR}/default"
    os.makedirs(d, exist_ok=True)
    key = f"{d}/privkey.pem"
    crt = f"{d}/fullchain.pem"
    if not (os.path.exists(key) and os.path.exists(crt)):
        subprocess.run([
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
            "-keyout", key, "-out", crt, "-days", "3650",
            "-subj", f"/CN={MAIL_HOSTNAME}",
        ], check=True)
    write(f"{GEN_CONFIG_DIR}/certs/default.pem", read(crt) + read(key))


def build_combined_pems(domains):
    for name in domains:
        d = cert_dir(name)
        write(f"{GEN_CONFIG_DIR}/certs/mail.{name}.pem", read(f"{d}/fullchain.pem") + read(f"{d}/privkey.pem"))


def reconcile_all(reload=True):
    session = SessionLocal()
    try:
        all_domains = [d.name for d in session.query(Domain).filter_by(active=True).order_by(Domain.name).all()]
    finally:
        session.close()

    certified = [name for name in all_domains if has_cert(name)]
    build_combined_pems(certified)

    write(f"{GEN_CONFIG_DIR}/postfix/sni", render("postfix-sni.j2", domains=certified))
    write(f"{GEN_CONFIG_DIR}/dovecot/sni.conf", render("dovecot-sni.conf.j2", domains=certified))
    write(f"{GEN_CONFIG_DIR}/haproxy/mail-465.crtlist", render("haproxy-crtlist.j2", domains=certified))
    write(f"{GEN_CONFIG_DIR}/haproxy/mail-993.crtlist", render("haproxy-crtlist.j2", domains=certified))
    write(f"{GEN_CONFIG_DIR}/opendkim/key.table", render("opendkim-key.table.j2", domains=all_domains))
    write(f"{GEN_CONFIG_DIR}/opendkim/signing.table", render("opendkim-signing.table.j2", domains=all_domains))
    write(f"{GEN_CONFIG_DIR}/opendkim/trusted.hosts", render("opendkim-trusted.hosts.j2", domains=all_domains))
    panel = panel_host()
    traefik_domains = [name for name in certified if f"mail.{name}" != panel]
    write(f"{GEN_CONFIG_DIR}/traefik/dynamic.yml", render(
        "traefik-dynamic.yml.j2",
        domains=traefik_domains,
        panel_host=panel,
        panel_allow=PANEL_ALLOW_IPS,
    ))

    if reload:
        reload_services.postfix_postmap()
        errors = reload_services.validate()
        if errors:
            raise RuntimeError("config validation failed, services not reloaded:\n" + "\n".join(errors))
        reload_services.opendkim_reload()
        reload_services.postfix_reload()
        reload_services.dovecot_reload()
        reload_services.haproxy_reload()
