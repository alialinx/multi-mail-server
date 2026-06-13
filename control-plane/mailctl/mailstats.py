import re
import subprocess
from datetime import datetime, timedelta

from sqlalchemy import delete, select

from .db import Domain, MailStat, SessionLocal

MONTHS = {
    "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05", "Jun": "06",
    "Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12",
}

TS_RE = re.compile(r"^(\w{3})\s+(\d{1,2})\s")
FROM_RE = re.compile(r": (\w+): from=<([^>]*)>,")
DELIVER_RE = re.compile(r": (\w+): to=<([^>]*)>,.*?relay=(\S+?),.* status=(\w+)")


def _day(line, year):
    m = TS_RE.match(line)
    if not m:
        return None
    mon = MONTHS.get(m.group(1))
    if not mon:
        return None
    return f"{year}-{mon}-{m.group(2).zfill(2)}"


def _domain_of(addr):
    return addr.split("@")[-1].lower() if "@" in addr else ""


def parse():
    result = subprocess.run(
        ["docker", "exec", "postfix", "cat", "/var/log/mail/postfix.log"],
        capture_output=True, text=True,
    )
    year = datetime.now().year

    session = SessionLocal()
    try:
        ours = {d.name for d in session.query(Domain).all()}
    finally:
        session.close()

    qid_from = {}          # queue id -> sender domain
    counts = {}            # (day, domain, direction) -> count

    for line in result.stdout.splitlines():
        fm = FROM_RE.search(line)
        if fm:
            qid_from[fm.group(1)] = _domain_of(fm.group(2))
            continue
        dm = DELIVER_RE.search(line)
        if not dm:
            continue
        qid, to, relay, status = dm.group(1), dm.group(2), dm.group(3).lower(), dm.group(4)
        day = _day(line, year)
        if not day:
            continue

        if status == "sent":
            if "dovecot" in relay or "lmtp" in relay:
                domain, direction = _domain_of(to), "in"
            else:
                domain, direction = qid_from.get(qid, ""), "out"
        elif status == "bounced":
            domain, direction = qid_from.get(qid, "") or _domain_of(to), "bounce"
        else:
            continue

        if domain not in ours:
            continue
        key = (day, domain, direction)
        counts[key] = counts.get(key, 0) + 1

    return counts


def update():
    counts = parse()
    if not counts:
        return {"updated": 0}
    days = {k[0] for k in counts}
    session = SessionLocal()
    try:
        session.execute(delete(MailStat).where(MailStat.day.in_(days)))
        for (day, domain, direction), count in counts.items():
            session.add(MailStat(day=day, domain=domain, direction=direction, count=count))
        session.commit()
    finally:
        session.close()
    return {"updated": len(counts)}


def series(days=30, domain=None):
    try:
        days = max(1, min(int(days), 90))
    except (TypeError, ValueError):
        days = 30
    end = datetime.now().date()
    axis = [(end - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]

    session = SessionLocal()
    try:
        query = select(MailStat).where(MailStat.day.in_(axis))
        if domain:
            query = query.where(MailStat.domain == domain)
        rows = session.scalars(query).all()
        all_domains = sorted({d.domain for d in session.scalars(select(MailStat)).all()})
    finally:
        session.close()

    agg = {"in": {}, "out": {}, "bounce": {}}
    for r in rows:
        if r.direction in agg:
            agg[r.direction][r.day] = agg[r.direction].get(r.day, 0) + r.count

    return {
        "days": axis,
        "in": [agg["in"].get(d, 0) for d in axis],
        "out": [agg["out"].get(d, 0) for d in axis],
        "bounce": [agg["bounce"].get(d, 0) for d in axis],
        "domains": all_domains,
    }
