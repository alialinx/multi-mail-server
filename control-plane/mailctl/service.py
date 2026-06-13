import subprocess

from sqlalchemy import select

from . import certs, checks, dkim, dns, mailqueue, reconcile, sieve, status, validators
from .db import Alias, Domain, SessionLocal, User, init_db
from .passwords import hash_password


class ServiceError(Exception):
    pass


def _get_domain(session, name):
    return session.scalar(select(Domain).where(Domain.name == name))


def _get_user(session, email):
    return session.scalar(select(User).where(User.email == email))


def initialize():
    init_db()
    reconcile.ensure_default_cert()
    reconcile.reconcile_all(reload=False)


def list_domains():
    session = SessionLocal()
    try:
        rows = session.query(Domain).order_by(Domain.name).all()
        return [{"id": d.id, "name": d.name, "active": d.active} for d in rows]
    finally:
        session.close()


def add_domain(name):
    if not validators.valid_domain(name):
        raise ServiceError(f"invalid domain: {name}")

    session = SessionLocal()
    try:
        if _get_domain(session, name):
            raise ServiceError(f"domain {name} already exists")
        session.add(Domain(name=name, active=True))
        session.commit()
    finally:
        session.close()

    dkim_value = dkim.generate_key(name)
    reconcile.reconcile_all()

    cert_issued = True
    cert_message = "certificate issued"
    try:
        certs.issue(name)
        reconcile.reconcile_all()
    except subprocess.CalledProcessError:
        cert_issued = False
        cert_message = f"certificate not issued yet, call POST /certs/issue/{name} after DNS is set"

    return {
        "name": name,
        "dns": dns.records(name, dkim_value),
        "cert_issued": cert_issued,
        "cert_message": cert_message,
    }


def remove_domain(name):
    session = SessionLocal()
    try:
        domain = _get_domain(session, name)
        if not domain:
            raise ServiceError(f"domain {name} not found")
        session.query(User).filter_by(domain_id=domain.id).delete()
        session.query(Alias).filter_by(domain_id=domain.id).delete()
        session.delete(domain)
        session.commit()
    finally:
        session.close()
    reconcile.reconcile_all()
    return {"name": name, "removed": True}


def set_domain_active(name, active):
    session = SessionLocal()
    try:
        domain = _get_domain(session, name)
        if not domain:
            raise ServiceError(f"domain {name} not found")
        domain.active = active
        session.commit()
    finally:
        session.close()
    reconcile.reconcile_all()
    return {"name": name, "active": active}


def domain_dns(name):
    session = SessionLocal()
    try:
        if not _get_domain(session, name):
            raise ServiceError(f"domain {name} not found")
    finally:
        session.close()
    return dns.records(name, dkim.record_for(name))


def check_domain(name):
    session = SessionLocal()
    try:
        if not _get_domain(session, name):
            raise ServiceError(f"domain {name} not found")
    finally:
        session.close()
    return checks.run(name)


def list_users(domain=None):
    session = SessionLocal()
    try:
        query = select(User).order_by(User.email)
        if domain:
            target = _get_domain(session, domain)
            if not target:
                raise ServiceError(f"domain {domain} not found")
            query = query.where(User.domain_id == target.id)
        rows = session.scalars(query).all()
        return [
            {
                "id": u.id,
                "email": u.email,
                "active": u.active,
                "quota_mb": u.quota // (1024 * 1024) if u.quota else 0,
                "autoreply": u.autoreply_active,
            }
            for u in rows
        ]
    finally:
        session.close()


def add_user(email, password, quota_mb=0):
    if not validators.valid_email(email):
        raise ServiceError(f"invalid email: {email}")
    if not password:
        raise ServiceError("password is required")

    domain_name = email.split("@", 1)[1]
    session = SessionLocal()
    try:
        domain = _get_domain(session, domain_name)
        if not domain:
            raise ServiceError(f"add the domain first: {domain_name}")
        if _get_user(session, email):
            raise ServiceError(f"user {email} already exists")
        user = User(
            domain_id=domain.id,
            email=email,
            password=hash_password(password),
            active=True,
            quota=quota_mb * 1024 * 1024,
        )
        session.add(user)
        session.commit()
        return {"id": user.id, "email": email, "active": True, "quota_mb": quota_mb}
    finally:
        session.close()


def set_password(email, password):
    if not password:
        raise ServiceError("password is required")
    session = SessionLocal()
    try:
        user = _get_user(session, email)
        if not user:
            raise ServiceError(f"user {email} not found")
        user.password = hash_password(password)
        session.commit()
    finally:
        session.close()
    return {"email": email}


def set_user_active(email, active):
    session = SessionLocal()
    try:
        user = _get_user(session, email)
        if not user:
            raise ServiceError(f"user {email} not found")
        user.active = active
        session.commit()
    finally:
        session.close()
    return {"email": email, "active": active}


def set_quota(email, quota_mb):
    session = SessionLocal()
    try:
        user = _get_user(session, email)
        if not user:
            raise ServiceError(f"user {email} not found")
        user.quota = quota_mb * 1024 * 1024
        session.commit()
    finally:
        session.close()
    return {"email": email, "quota_mb": quota_mb}


def set_autoreply(email, active, subject="", text=""):
    session = SessionLocal()
    try:
        user = _get_user(session, email)
        if not user:
            raise ServiceError(f"user {email} not found")
        user.autoreply_active = active
        user.autoreply_subject = subject
        user.autoreply_text = text
        session.commit()
    finally:
        session.close()

    if active:
        sieve.write_vacation(email, subject, text)
    else:
        sieve.remove(email)
    return {"email": email, "autoreply": active}


def remove_user(email):
    session = SessionLocal()
    try:
        user = _get_user(session, email)
        if not user:
            raise ServiceError(f"user {email} not found")
        session.delete(user)
        session.commit()
    finally:
        session.close()
    sieve.remove(email)
    return {"email": email, "removed": True}


def list_aliases():
    session = SessionLocal()
    try:
        rows = session.query(Alias).order_by(Alias.address).all()
        return [{"id": a.id, "address": a.address, "goto": a.goto_address} for a in rows]
    finally:
        session.close()


def add_alias(address, goto, keep_copy=False):
    if not validators.valid_alias_address(address):
        raise ServiceError(f"invalid address: {address}")
    if not validators.valid_email(goto):
        raise ServiceError(f"invalid target: {goto}")

    domain_name = address.split("@", 1)[1]
    session = SessionLocal()
    try:
        domain = _get_domain(session, domain_name)
        if not domain:
            raise ServiceError(f"add the domain first: {domain_name}")
        if keep_copy and validators.valid_email(address):
            session.add(Alias(domain_id=domain.id, address=address, goto_address=address, active=True))
        session.add(Alias(domain_id=domain.id, address=address, goto_address=goto, active=True))
        session.commit()
    finally:
        session.close()
    return {"address": address, "goto": goto, "keep_copy": keep_copy}


def remove_alias(address, goto=None):
    session = SessionLocal()
    try:
        query = session.query(Alias).filter_by(address=address)
        if goto:
            query = query.filter_by(goto_address=goto)
        deleted = query.delete()
        session.commit()
    finally:
        session.close()
    if not deleted:
        raise ServiceError(f"alias {address} not found")
    return {"address": address, "removed": True}


def issue_cert(name):
    if not validators.valid_domain(name):
        raise ServiceError(f"invalid domain: {name}")
    certs.issue(name)
    reconcile.reconcile_all()
    return {"domain": name, "issued": True}


def renew_certs():
    certs.renew()
    reconcile.reconcile_all()
    return {"renewed": True}


def get_status():
    return status.get_status()


def list_queue():
    return mailqueue.list_queue()


def flush_queue():
    return mailqueue.flush_queue()


def delete_queue(queue_id):
    if queue_id.upper() != "ALL" and not mailqueue.QUEUE_ID_RE.match(queue_id):
        raise ServiceError(f"invalid queue id: {queue_id}")
    return mailqueue.delete(queue_id)
