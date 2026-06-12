from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

from .. import auth, service
from ..service import ServiceError

app = FastAPI(title="Mail Platform API", version="0.1.0")

oauth2 = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)


@app.post("/token")
def login(form: OAuth2PasswordRequestForm = Depends()):
    if not auth.check_login(form.username, form.password):
        raise HTTPException(status_code=401, detail="invalid credentials")
    return {"access_token": auth.create_token(form.username), "token_type": "bearer"}


def authorize(token: str = Depends(oauth2)):
    if token and auth.verify_token(token):
        return
    raise HTTPException(status_code=401, detail="not authenticated")


def run(action):
    try:
        return action()
    except ServiceError as error:
        raise HTTPException(status_code=400, detail=str(error))


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
    return {"status": "ok"}


api = APIRouter(dependencies=[Depends(authorize)])


@api.get("/domains")
def list_domains():
    return service.list_domains()


@api.post("/domains")
def add_domain(body: DomainIn):
    return run(lambda: service.add_domain(body.name))


@api.get("/domains/{name}/dns")
def domain_dns(name: str):
    return {"records": run(lambda: service.domain_dns(name))}


@api.get("/domains/{name}/check")
def check_domain(name: str):
    return {"domain": name, "checks": run(lambda: service.check_domain(name))}


@api.post("/domains/{name}/enable")
def enable_domain(name: str):
    run(lambda: service.set_domain_active(name, True))
    return {"name": name, "active": True}


@api.post("/domains/{name}/disable")
def disable_domain(name: str):
    run(lambda: service.set_domain_active(name, False))
    return {"name": name, "active": False}


@api.delete("/domains/{name}")
def remove_domain(name: str):
    run(lambda: service.remove_domain(name))
    return {"removed": name}


@api.get("/users")
def list_users(domain: str = None):
    return run(lambda: service.list_users(domain))


@api.post("/users")
def add_user(body: UserIn):
    run(lambda: service.add_user(body.email, body.password, body.quota_mb))
    return {"email": body.email}


@api.put("/users/{email}/password")
def set_password(email: str, body: PasswordIn):
    run(lambda: service.set_password(email, body.password))
    return {"email": email}


@api.post("/users/{email}/enable")
def enable_user(email: str):
    run(lambda: service.set_user_active(email, True))
    return {"email": email, "active": True}


@api.post("/users/{email}/disable")
def disable_user(email: str):
    run(lambda: service.set_user_active(email, False))
    return {"email": email, "active": False}


@api.put("/users/{email}/quota")
def set_quota(email: str, body: QuotaIn):
    run(lambda: service.set_quota(email, body.quota_mb))
    return {"email": email, "quota_mb": body.quota_mb}


@api.put("/users/{email}/autoreply")
def set_autoreply(email: str, body: AutoreplyIn):
    run(lambda: service.set_autoreply(email, body.active, body.subject, body.text))
    return {"email": email, "autoreply": body.active}


@api.delete("/users/{email}")
def remove_user(email: str):
    run(lambda: service.remove_user(email))
    return {"removed": email}


@api.get("/aliases")
def list_aliases():
    return service.list_aliases()


@api.post("/aliases")
def add_alias(body: AliasIn):
    run(lambda: service.add_alias(body.address, body.goto, body.keep_copy))
    return {"address": body.address, "goto": body.goto}


@api.delete("/aliases")
def remove_alias(address: str, goto: str = None):
    run(lambda: service.remove_alias(address, goto))
    return {"removed": address}


@api.post("/certs/issue/{domain}")
def issue_cert(domain: str):
    run(lambda: service.issue_cert(domain))
    return {"domain": domain}


@api.post("/certs/renew")
def renew_certs():
    service.renew_certs()
    return {"status": "renewed"}


app.include_router(api)
