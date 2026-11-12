import asyncio
import os
import time
from collections import defaultdict, deque

DEFAULT_LIMIT = int(os.environ.get("RATE_LIMIT_PER_HOUR", "250"))
NOREPLY_LIMIT = int(os.environ.get("RATE_LIMIT_NOREPLY_PER_HOUR", "2000"))
WINDOW_SECONDS = 3600
PORT = 10040

sent = defaultdict(deque)
limited = set()


def limit_for(user):
    if user.startswith("noreply@"):
        return NOREPLY_LIMIT
    return DEFAULT_LIMIT


def sent_last_hour(user, now):
    history = sent[user]
    while history and history[0][0] <= now - WINDOW_SECONDS:
        history.popleft()
    return sum(count for _, count in history)


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

    if total + recipients > limit:
        if user not in limited:
            limited.add(user)
            print(f"LIMIT {user}: {total} recipients in the last hour, limit {limit}, client {attrs.get('client_address', '')}", flush=True)
        return f"450 4.7.1 Sending limit reached ({limit} recipients per hour), try again later"

    if user in limited:
        limited.discard(user)
        print(f"RESUME {user}: back under the limit", flush=True)

    sent[user].append((now, recipients))
    return "DUNNO"


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


async def handle(reader, writer):
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


async def main():
    server = await asyncio.start_server(handle, "0.0.0.0", PORT)
    print(f"ratelimit listening on {PORT}: default {DEFAULT_LIMIT}/hour, noreply@ {NOREPLY_LIMIT}/hour", flush=True)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
