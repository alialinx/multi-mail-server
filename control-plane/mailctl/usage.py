import subprocess


def usage():
    """Map of email -> mailbox storage usage, from `doveadm quota get -A`."""
    result = subprocess.run(
        ["docker", "exec", "dovecot", "doveadm", "quota", "get", "-A"],
        capture_output=True, text=True,
    )
    out = {}
    for line in result.stdout.splitlines():
        parts = line.split()
        # columns: <user> User quota STORAGE <value> <limit> <percent>
        if "STORAGE" not in parts:
            continue
        i = parts.index("STORAGE")
        email = parts[0]
        value = parts[i + 1] if i + 1 < len(parts) else "0"
        limit = parts[i + 2] if i + 2 < len(parts) else "-"
        used_kb = int(value) if value.isdigit() else 0
        limit_kb = int(limit) if limit.isdigit() else 0
        percent = round(used_kb / limit_kb * 100, 1) if limit_kb > 0 else 0
        out[email] = {"used_mb": round(used_kb / 1024, 1), "percent": percent}
    return out
