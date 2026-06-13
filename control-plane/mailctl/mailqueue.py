import json
import re
import subprocess

QUEUE_ID_RE = re.compile(r"^[A-Za-z0-9]+$")


def list_queue():
    result = subprocess.run(
        ["docker", "exec", "postfix", "postqueue", "-j"],
        capture_output=True, text=True,
    )
    items = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        recipients = msg.get("recipients", [])
        reason = next((r.get("delay_reason") for r in recipients if r.get("delay_reason")), "")
        items.append({
            "id": msg.get("queue_id"),
            "queue": msg.get("queue_name"),
            "sender": msg.get("sender"),
            "recipients": [r.get("address") for r in recipients],
            "reason": reason,
            "size": msg.get("message_size"),
            "arrival_time": msg.get("arrival_time"),
        })
    return items


def flush_queue():
    subprocess.run(["docker", "exec", "postfix", "postqueue", "-f"], check=True)
    return {"flushed": True}


def delete(queue_id):
    target = "ALL" if queue_id.upper() == "ALL" else queue_id
    subprocess.run(["docker", "exec", "postfix", "postsuper", "-d", target], check=True)
    return {"deleted": target}
