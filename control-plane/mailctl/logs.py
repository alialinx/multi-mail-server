import subprocess

SOURCES = {
    "postfix": ("postfix", "/var/log/mail/postfix.log"),
    "dovecot": ("dovecot", "/var/log/mail/dovecot.log"),
}


def tail(source="postfix", q="", limit=200, include_noise=False):
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
        # fetch extra so we still return `limit` real lines after dropping noise
        fetch = limit if include_noise else min(limit * 6, 6000)
        result = subprocess.run(
            ["docker", "exec", container, "tail", "-n", str(fetch), path],
            capture_output=True, text=True,
        )

    lines = [line for line in result.stdout.splitlines() if line.strip()]
    if not include_noise:
        # HAProxy health-check chatter is all from localhost (127.0.0.1);
        # real client/relay lines carry the actual IP, so this is safe to hide.
        lines = [line for line in lines if "127.0.0.1" not in line]
    return {"source": source, "lines": lines[-limit:]}
