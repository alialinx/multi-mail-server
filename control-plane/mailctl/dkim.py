import base64
import os

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from .config import DKIM_KEYS_DIR


def key_path(domain):
    return os.path.join(DKIM_KEYS_DIR, domain, "default.private")


def generate_key(domain):
    path = key_path(domain)
    if os.path.exists(path):
        return record_for(domain)

    os.makedirs(os.path.dirname(path), exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )
    with open(path, "wb") as f:
        f.write(pem)
    os.chmod(path, 0o644)
    return record_for(domain)


def record_for(domain):
    with open(key_path(domain), "rb") as f:
        key = serialization.load_pem_private_key(f.read(), password=None)
    pub = key.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return "v=DKIM1; k=rsa; p=" + base64.b64encode(pub).decode()
