import subprocess


def run(cmd):
    subprocess.run(cmd, check=True)


def validate():
    checks = {
        "postfix": ["docker", "exec", "postfix", "postfix", "check"],
        "haproxy": ["docker", "exec", "haproxy", "haproxy", "-c", "-f", "/usr/local/etc/haproxy/haproxy.cfg"],
        "dovecot": ["docker", "exec", "dovecot", "doveconf"],
    }
    errors = []
    for name, cmd in checks.items():
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip()
            errors.append(f"{name}: {message}")
    return errors


def postfix_postmap():
    run(["docker", "exec", "postfix", "postmap", "-F", "hash:/gen-config/postfix/sni"])


def postfix_reload():
    run(["docker", "exec", "postfix", "postfix", "reload"])


def dovecot_reload():
    run(["docker", "exec", "dovecot", "doveadm", "reload"])


def haproxy_reload():
    run(["docker", "restart", "haproxy"])


def opendkim_reload():
    run(["docker", "restart", "opendkim"])
