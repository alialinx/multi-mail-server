import asyncio
import threading
import time

from fastapi import APIRouter, Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from .. import auth, logs, service
from ..db import init_db
from ..service import ServiceError

app = FastAPI(title="Mail Platform API", version="0.1.0")

RENEW_INTERVAL_SECONDS = 12 * 3600
MAILSTATS_INTERVAL_SECONDS = 600


def _renew_loop():
    # certbot only renews certs that are close to expiry, so running this twice
    # a day is safe and removes the need for a manual cron job on the host.
    time.sleep(600)
    while True:
        try:
            service.renew_certs()
        except Exception:
            pass
        time.sleep(RENEW_INTERVAL_SECONDS)


def _mailstats_loop():
    while True:
        try:
            service.update_mailstats()
        except Exception:
            pass
        time.sleep(MAILSTATS_INTERVAL_SECONDS)


@app.on_event("startup")
def start_background():
    try:
        init_db()   # ensure newer tables (e.g. mail_stats) exist on upgrades
    except Exception:
        pass
    threading.Thread(target=_renew_loop, daemon=True).start()
    threading.Thread(target=_mailstats_loop, daemon=True).start()


@app.websocket("/ws/logs")
async def ws_logs(ws: WebSocket, source: str = "postfix", token: str = "", noise: bool = False):
    # browsers can't set auth headers on a WebSocket, so the token comes as a query param
    if not auth.verify_token(token):
        await ws.close(code=1008)
        return
    await ws.accept()
    container, path = logs.SOURCES.get(source, logs.SOURCES["postfix"])
    proc = await asyncio.create_subprocess_exec(
        "docker", "exec", container, "tail", "-n", "50", "-F", path,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            text = line.decode("utf-8", "replace").rstrip("\n")
            if not text or (not noise and "127.0.0.1" in text):
                continue
            await ws.send_text(text)
    except (WebSocketDisconnect, ConnectionError, RuntimeError):
        pass
    finally:
        try:
            proc.terminate()
        except ProcessLookupError:
            pass
        try:
            await proc.wait()
        except Exception:
            pass

oauth2 = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)


def ok(data):
    return {"ok": True, "data": data}


@app.exception_handler(ServiceError)
async def handle_service_error(request, exc):
    return JSONResponse(status_code=400, content={"ok": False, "error": str(exc)})


@app.exception_handler(StarletteHTTPException)
async def handle_http_error(request, exc):
    return JSONResponse(status_code=exc.status_code, content={"ok": False, "error": exc.detail})


@app.exception_handler(Exception)
async def handle_unexpected_error(request, exc):
    return JSONResponse(status_code=500, content={"ok": False, "error": str(exc)})


@app.post("/token")
def login(form: OAuth2PasswordRequestForm = Depends()):
    if not auth.check_login(form.username, form.password):
        raise StarletteHTTPException(status_code=401, detail="invalid credentials")
    return {"access_token": auth.create_token(form.username), "token_type": "bearer"}


def authorize(token: str = Depends(oauth2)):
    if token and auth.verify_token(token):
        return
    raise StarletteHTTPException(status_code=401, detail="not authenticated")


class DomainIn(BaseModel):
    name: str


class UserIn(BaseModel):
    email: str
    password: str
    quota_mb: int = 0


class PasswordIn(BaseModel):
    password: str


class QuotaIn(BaseModel):
    quota_mb: int


class AutoreplyIn(BaseModel):
    active: bool
    subject: str = ""
    text: str = ""


class AliasIn(BaseModel):
    address: str
    goto: str
    keep_copy: bool = False


@app.get("/health")
def health():
    return {"ok": True, "data": {"status": "ok"}}


api = APIRouter(dependencies=[Depends(authorize)])


@api.get("/domains")
def list_domains():
    return ok(service.list_domains())


@api.post("/domains")
def add_domain(body: DomainIn):
    return ok(service.add_domain(body.name))


@api.get("/domains/{name}/dns")
def domain_dns(name: str):
    return ok(service.domain_dns(name))


@api.get("/domains/{name}/check")
def check_domain(name: str):
    return ok(service.check_domain(name))


@api.post("/domains/{name}/enable")
def enable_domain(name: str):
    return ok(service.set_domain_active(name, True))


@api.post("/domains/{name}/disable")
def disable_domain(name: str):
    return ok(service.set_domain_active(name, False))


@api.delete("/domains/{name}")
def remove_domain(name: str):
    return ok(service.remove_domain(name))


@api.get("/users")
def list_users(domain: str = None):
    return ok(service.list_users(domain))


@api.get("/users/usage")
def users_usage():
    return ok(service.users_usage())


@api.post("/users")
def add_user(body: UserIn):
    return ok(service.add_user(body.email, body.password, body.quota_mb))


@api.put("/users/{email}/password")
def set_password(email: str, body: PasswordIn):
    return ok(service.set_password(email, body.password))


@api.post("/users/{email}/enable")
def enable_user(email: str):
    return ok(service.set_user_active(email, True))


@api.post("/users/{email}/disable")
def disable_user(email: str):
    return ok(service.set_user_active(email, False))


@api.put("/users/{email}/quota")
def set_quota(email: str, body: QuotaIn):
    return ok(service.set_quota(email, body.quota_mb))


@api.put("/users/{email}/autoreply")
def set_autoreply(email: str, body: AutoreplyIn):
    return ok(service.set_autoreply(email, body.active, body.subject, body.text))


@api.delete("/users/{email}")
def remove_user(email: str):
    return ok(service.remove_user(email))


@api.get("/aliases")
def list_aliases():
    return ok(service.list_aliases())


@api.post("/aliases")
def add_alias(body: AliasIn):
    return ok(service.add_alias(body.address, body.goto, body.keep_copy))


@api.delete("/aliases")
def remove_alias(address: str, goto: str = None):
    return ok(service.remove_alias(address, goto))


@api.post("/certs/issue/{domain}")
def issue_cert(domain: str):
    return ok(service.issue_cert(domain))


@api.post("/certs/renew")
def renew_certs():
    return ok(service.renew_certs())


@api.get("/status")
def status():
    return ok(service.get_status())


@api.get("/stats")
def stats():
    return ok(service.get_stats())


@api.get("/mailstats")
def mailstats(days: int = 30, domain: str = ""):
    return ok(service.mail_series(days, domain or None))


@api.get("/logs")
def logs(source: str = "postfix", q: str = "", limit: int = 200, noise: bool = False):
    return ok(service.get_logs(source, q, limit, noise))


@api.get("/fail2ban")
def fail2ban_status():
    return ok(service.fail2ban_status())


@api.delete("/fail2ban/banned/{ip}")
def fail2ban_unban(ip: str):
    return ok(service.fail2ban_unban(ip))


@api.get("/queue")
def list_queue():
    return ok(service.list_queue())


@api.post("/queue/flush")
def flush_queue():
    return ok(service.flush_queue())


@api.delete("/queue/{queue_id}")
def delete_queue(queue_id: str):
    return ok(service.delete_queue(queue_id))


app.include_router(api)
