import asyncio
import json
import os
import signal
import time
from collections import defaultdict, deque

DEFAULT_LIMIT = int(os.environ.get("RATE_LIMIT_PER_HOUR", "250"))
NOREPLY_LIMIT = int(os.environ.get("RATE_LIMIT_NOREPLY_PER_HOUR", "2000"))
LIMITS_FILE = os.environ.get("RATE_LIMIT_LIMITS_FILE", "/gen-config/ratelimit/limits.json")
STATE_FILE = os.environ.get("RATE_LIMIT_STATE_FILE", "/data/state.json")
POLICY_PORT = 10040
HTTP_PORT = 10041
WINDOW_SECONDS = 3600
KEEP_HOURS = 24 * 7

recent = defaultdict(deque)
hourly = defaultdict(dict)
deferred = defaultdict(dict)
last_sent = {}
last_client = {}
last_limited = {}
limited = set()

custom_limits = {}
limits_mtime = None


def load_custom_limits():
    global custom_limits, limits_mtime
    try:
        mtime = os.path.getmtime(LIMITS_FILE)
    except OSError:
        custom_limits = {}
        limits_mtime = None
        return
    if mtime == limits_mtime:
        return
    try:
        with open(LIMITS_FILE) as f:
            data = json.load(f)
        custom_limits = {k.lower(): int(v) for k, v in data.items()}
        limits_mtime = mtime
        print(f"loaded {len(custom_limits)} custom limits", flush=True)
    except (OSError, ValueError) as e:
        print(f"could not read {LIMITS_FILE}: {e}", flush=True)


def default_limit_for(user):
    if user.startswith("noreply@"):
        return NOREPLY_LIMIT
    return DEFAULT_LIMIT


def limit_for(user):
    load_custom_limits()
    if user in custom_limits:
        return custom_limits[user]
    return default_limit_for(user)


def current_hour(now):
    return int(now // 3600)


def sent_last_hour(user, now):
    history = recent[user]
    while history and history[0][0] <= now - WINDOW_SECONDS:
        history.popleft()
    return sum(count for _, count in history)


def sum_hours(buckets, now, hours):
    first = current_hour(now) - hours + 1
    return sum(count for hour, count in buckets.items() if hour >= first)


def add_to_bucket(buckets, now, count):
    hour = current_hour(now)
    buckets[hour] = buckets.get(hour, 0) + count


def prune(now):
    oldest = current_hour(now) - KEEP_HOURS
    for store in (hourly, deferred):
        for user in list(store):
            for hour in [h for h in store[user] if h <= oldest]:
                del store[user][hour]
            if not store[user]:
                del store[user]


def check(attrs):
    user = attrs.get("sasl_username", "").strip().lower()
    if not user:
        return "DUNNO"

    try:
        recipients = int(attrs.get("recipient_count", "1"))
    except ValueError:
        recipients = 1
    if recipients < 1:
        recipients = 1

    now = time.time()
    limit = limit_for(user)
    total = sent_last_hour(user, now)
    client = attrs.get("client_address", "")

    if total + recipients > limit:
        add_to_bucket(deferred[user], now, recipients)
        last_limited[user] = now
        if user not in limited:
            limited.add(user)
            print(f"LIMIT {user}: {total} recipients in the last hour, limit {limit}, client {client}", flush=True)
        return f"450 4.7.1 Sending limit reached ({limit} recipients per hour), try again later"

    if user in limited:
        limited.discard(user)
        print(f"RESUME {user}: back under the limit", flush=True)

    recent[user].append((now, recipients))
    add_to_bucket(hourly[user], now, recipients)
    last_sent[user] = now
    last_client[user] = client
    return "DUNNO"


def usage():
    now = time.time()
    prune(now)
    load_custom_limits()
    users = set(hourly) | set(deferred) | set(recent) | set(custom_limits)
    accounts = []
    for user in sorted(users):
        limit = limit_for(user)
        last_hour = sent_last_hour(user, now)
        accounts.append({
            "address": user,
            "limit": limit,
            "custom": user in custom_limits,
            "last_hour": last_hour,
            "percent": round(last_hour / limit * 100) if limit else 0,
            "last_24h": sum_hours(hourly.get(user, {}), now, 24),
            "last_7d": sum_hours(hourly.get(user, {}), now, KEEP_HOURS),
            "deferred_24h": sum_hours(deferred.get(user, {}), now, 24),
            "limited_now": user in limited,
            "last_sent_at": last_sent.get(user),
            "last_limited_at": last_limited.get(user),
            "last_client": last_client.get(user, ""),
        })
    return {
        "default_limit": DEFAULT_LIMIT,
        "noreply_limit": NOREPLY_LIMIT,
        "accounts": accounts,
    }


def save_state():
    state = {
        "recent": {u: list(h) for u, h in recent.items() if h},
        "hourly": {u: {str(h): c for h, c in b.items()} for u, b in hourly.items()},
        "deferred": {u: {str(h): c for h, c in b.items()} for u, b in deferred.items()},
        "last_sent": last_sent,
        "last_client": last_client,
        "last_limited": last_limited,
    }
    tmp = STATE_FILE + ".tmp"
    try:
        with open(tmp, "w") as f:
            json.dump(state, f)
        os.replace(tmp, STATE_FILE)
    except OSError as e:
        print(f"could not save state: {e}", flush=True)


def load_state():
    try:
        with open(STATE_FILE) as f:
            state = json.load(f)
    except (OSError, ValueError):
        return
    for user, items in state.get("recent", {}).items():
        recent[user] = deque((t, c) for t, c in items)
    for user, buckets in state.get("hourly", {}).items():
        hourly[user] = {int(h): c for h, c in buckets.items()}
    for user, buckets in state.get("deferred", {}).items():
        deferred[user] = {int(h): c for h, c in buckets.items()}
    last_sent.update(state.get("last_sent", {}))
    last_client.update(state.get("last_client", {}))
    last_limited.update(state.get("last_limited", {}))
    print(f"loaded state for {len(hourly)} accounts", flush=True)


async def read_request(reader):
    attrs = {}
    while True:
        line = await reader.readline()
        if not line:
            return None
        line = line.decode(errors="replace").rstrip("\r\n")
        if line == "":
            return attrs
        if "=" in line:
            key, value = line.split("=", 1)
            attrs[key] = value


async def handle_policy(reader, writer):
    try:
        while True:
            attrs = await read_request(reader)
            if attrs is None:
                break
            writer.write(f"action={check(attrs)}\n\n".encode())
            await writer.drain()
    except ConnectionError:
        pass
    finally:
        writer.close()


async def handle_http(reader, writer):
    try:
        request_line = await reader.readline()
        while True:
            line = await reader.readline()
            if not line or line in (b"\r\n", b"\n"):
                break
        parts = request_line.decode(errors="replace").split()
        if len(parts) >= 2 and parts[0] == "GET" and parts[1] == "/usage":
            body = json.dumps(usage()).encode()
            status = "200 OK"
        else:
            body = b'{"error": "not found"}'
            status = "404 Not Found"
        writer.write(
            f"HTTP/1.1 {status}\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
            + body
        )
        await writer.drain()
    except ConnectionError:
        pass
    finally:
        writer.close()


async def save_every_minute():
    while True:
        await asyncio.sleep(60)
        prune(time.time())
        save_state()


async def main():
    load_state()
    load_custom_limits()
    policy = await asyncio.start_server(handle_policy, "0.0.0.0", POLICY_PORT)
    http = await asyncio.start_server(handle_http, "0.0.0.0", HTTP_PORT)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    saver = asyncio.create_task(save_every_minute())
    print(f"ratelimit listening on {POLICY_PORT} (policy) and {HTTP_PORT} (usage): default {DEFAULT_LIMIT}/hour, noreply@ {NOREPLY_LIMIT}/hour", flush=True)
    await stop.wait()

    saver.cancel()
    policy.close()
    http.close()
    save_state()
    print("state saved, exiting", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
