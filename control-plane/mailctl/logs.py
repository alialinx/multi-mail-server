import subprocess

SOURCES = {
    "postfix": ("postfix", "/var/log/mail/postfix.log"),
    "dovecot": ("dovecot", "/var/log/mail/dovecot.log"),
}


def tail(source="postfix", q="", limit=200):
    if source not in SOURCES:
        source = "postfix"
    try:
        limit = max(1, min(int(limit), 1000))
    except (TypeError, ValueError):
        limit = 200
    container, path = SOURCES[source]

    if q:
        # list args (no shell) + `--` so a query starting with "-" is safe
        result = subprocess.run(
            ["docker", "exec", container, "grep", "-i", "--", q, path],
            capture_output=True, text=True,
        )
    else:
        result = subprocess.run(
            ["docker", "exec", container, "tail", "-n", str(limit), path],
            capture_output=True, text=True,
        )
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    return {"source": source, "lines": lines[-limit:]}
