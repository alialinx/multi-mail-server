import subprocess

from .config import ACME_EMAIL, ACME_SERVER

CONFIG_ARGS = [
    "--config-dir", "/certs",
    "--work-dir", "/certs/work",
    "--logs-dir", "/certs/logs",
    "--webroot", "-w", "/var/www/certbot",
]


def issue(domain):
    cmd = [
        "docker", "exec", "certbot", "certbot", "certonly",
        "--non-interactive", "--agree-tos",
        "--email", ACME_EMAIL,
        "--server", ACME_SERVER,
        "--cert-name", f"mail.{domain}",
        *CONFIG_ARGS,
        "-d", f"mail.{domain}",
        "-d", f"autodiscover.{domain}",
    ]
    subprocess.run(cmd, check=True)


def renew():
    cmd = ["docker", "exec", "certbot", "certbot", "renew", *CONFIG_ARGS]
    subprocess.run(cmd, check=True)
