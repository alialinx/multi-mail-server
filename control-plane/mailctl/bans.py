import re
import subprocess

IP_RE = re.compile(r"^[0-9a-fA-F:.]+$")


def _jails():
    result = subprocess.run(
        ["docker", "exec", "fail2ban", "fail2ban-client", "status"],
        capture_output=True, text=True,
    )
    for line in result.stdout.splitlines():
        if "Jail list:" in line:
            return [x.strip() for x in line.split(":", 1)[1].split(",") if x.strip()]
    return []


def status():
    out = []
    for jail in _jails():
        result = subprocess.run(
            ["docker", "exec", "fail2ban", "fail2ban-client", "status", jail],
            capture_output=True, text=True,
        )
        banned = []
        for line in result.stdout.splitlines():
            if "Banned IP list:" in line:
                banned = line.split(":", 1)[1].split()
        out.append({"jail": jail, "banned": banned, "count": len(banned)})
    return out


def unban(ip):
    subprocess.run(
        ["docker", "exec", "fail2ban", "fail2ban-client", "unban", ip],
        check=True,
    )
    return {"unbanned": ip}
