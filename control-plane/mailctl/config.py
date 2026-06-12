import os

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+psycopg://mailservers:changeme@postgres:5432/mailservers")
SERVER_IP = os.environ.get("SERVER_IP", "127.0.0.1")
MAIL_HOSTNAME = os.environ.get("MAIL_HOSTNAME", "localhost")
ACME_EMAIL = os.environ.get("ACME_EMAIL", "")
ACME_SERVER = os.environ.get("ACME_SERVER", "https://acme-v02.api.letsencrypt.org/directory")

GEN_CONFIG_DIR = "/gen-config"
CERTS_DIR = "/certs"
DKIM_KEYS_DIR = "/etc/opendkim/keys"
ACME_WEBROOT = "/var/www/certbot"
SIEVE_DIR = "/var/sieve"

API_KEY = os.environ.get("API_KEY", "")
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
JWT_SECRET = os.environ.get("JWT_SECRET", "")
TOKEN_TTL_SECONDS = 8 * 3600
