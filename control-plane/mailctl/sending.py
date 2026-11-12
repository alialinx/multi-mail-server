import json
import os
import re
import subprocess
import urllib.request

from .config import GEN_CONFIG_DIR, RATE_LIMIT_NOREPLY_PER_HOUR, RATE_LIMIT_PER_HOUR
from .db import SendLimit, SessionLocal, User

LIMITS_FILE = f"{GEN_CONFIG_DIR}/ratelimit/limits.json"
USAGE_URL = "http://ratelimit:10041/usage"
LOG_PATH = "/var/log/mail/postfix.log"
MAX_LIMIT = 100000

QUEUE_ID_RE = re.compile(r": ([0-9A-F]{6,}): ")
DELIVERY_RE = re.compile(r"^(\w{3}\s+\d+ [\d:]+) .*?: ([0-9A-F]{6,}): to=<([^>]*)>,.*? status=(\w+) \((.*)\)$")
ACCEPT_RE = re.compile(r"^(\w{3}\s+\d+ [\d:]+) .*?: ([0-9A-F]{6,}): client=([^,]*), sasl_method=\w+, sasl_username=(\S+)")


def default_limit(address):
    if address.startswith("noreply@"):
        return RATE_LIMIT_NOREPLY_PER_HOUR
    return RATE_LIMIT_PER_HOUR


def custom_limits():
    session = SessionLocal()
    try:
        return {row.address: row.per_hour for row in session.query(SendLimit).all()}
    finally:
        session.close()


def write_limits_file():
    os.makedirs(os.path.dirname(LIMITS_FILE), exist_ok=True)
    tmp = LIMITS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(custom_limits(), f)
    os.replace(tmp, LIMITS_FILE)


def fetch_usage():
    with urllib.request.urlopen(USAGE_URL, timeout=5) as resp:
        return json.load(resp)


def empty_row(address, limit, custom):
    return {
        "address": address,
        "limit": limit,
        "custom": custom,
        "last_hour": 0,
        "percent": 0,
        "last_24h": 0,
        "last_7d": 0,
        "deferred_24h": 0,
        "limited_now": False,
        "last_sent_at": None,
        "last_limited_at": None,
        "last_client": "",
    }


def overview():
    try:
        live = fetch_usage()["accounts"]
        available = True
    except Exception:
        live = []
        available = False

    limits = custom_limits()
    session = SessionLocal()
    try:
        mailboxes = {u.email.lower() for u in session.query(User).all()}
    finally:
        session.close()

    by_address = {row["address"]: row for row in live}
    rows = []
    for address in sorted(mailboxes | set(by_address)):
        custom = address in limits
        limit = limits.get(address, default_limit(address))
        row = by_address.get(address) or empty_row(address, limit, custom)
        row["limit"] = limit
        row["custom"] = custom
        row["percent"] = round(row["last_hour"] / limit * 100) if limit else 0
        row["mailbox"] = address in mailboxes
        rows.append(row)

    rows.sort(key=lambda r: (-r["last_24h"], r["address"]))
    return {
        "available": available,
        "default_limit": RATE_LIMIT_PER_HOUR,
        "noreply_limit": RATE_LIMIT_NOREPLY_PER_HOUR,
        "accounts": rows,
    }


def set_limit(address, per_hour):
    session = SessionLocal()
    try:
        row = session.query(SendLimit).filter_by(address=address).first()
        if per_hour is None:
            if row:
                session.delete(row)
        elif row:
            row.per_hour = per_hour
        else:
            session.add(SendLimit(address=address, per_hour=per_hour))
        session.commit()
    finally:
        session.close()
    write_limits_file()


def grep_log(patterns):
    cmd = ["docker", "exec", "postfix", "grep", "-F"]
    for p in patterns:
        cmd += ["-e", p]
    cmd += ["--", LOG_PATH]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout.splitlines()


def recent_messages(address, limit=50):
    accepted = []
    for line in grep_log([f"sasl_username={address}"]):
        m = ACCEPT_RE.match(line)
        if m and m.group(4).lower() == address:
            accepted.append({"time": m.group(1), "queue_id": m.group(2), "client": m.group(3)})
    accepted = accepted[-limit:]
    if not accepted:
        return []

    by_id = {a["queue_id"]: dict(a, recipients=[]) for a in accepted}
    for line in grep_log([f": {qid}: to=<" for qid in by_id]):
        m = DELIVERY_RE.match(line)
        if not m or m.group(2) not in by_id:
            continue
        recipients = by_id[m.group(2)]["recipients"]
        entry = {"to": m.group(3), "status": m.group(4), "detail": m.group(5)[:200], "time": m.group(1)}
        for i, existing in enumerate(recipients):
            if existing["to"] == entry["to"]:
                recipients[i] = entry
                break
        else:
            recipients.append(entry)

    return list(reversed([by_id[a["queue_id"]] for a in accepted]))
