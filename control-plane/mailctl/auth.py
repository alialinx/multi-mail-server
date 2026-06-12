import hmac
import time

import jwt

from .config import ADMIN_PASSWORD, ADMIN_USER, JWT_SECRET, TOKEN_TTL_SECONDS


def check_login(username, password):
    if not ADMIN_PASSWORD:
        return False
    user_ok = hmac.compare_digest(username, ADMIN_USER)
    password_ok = hmac.compare_digest(password, ADMIN_PASSWORD)
    return user_ok and password_ok


def create_token(username):
    payload = {"sub": username, "exp": int(time.time()) + TOKEN_TTL_SECONDS}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def verify_token(token):
    try:
        jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return True
    except jwt.PyJWTError:
        return False
