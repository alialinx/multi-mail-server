#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v docker >/dev/null 2>&1; then
    echo "docker is not installed"
    exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
    echo "docker compose plugin is not installed"
    exit 1
fi

if [ ! -f .env ]; then
    detected_ip="$(curl -fsS https://api.ipify.org || echo 127.0.0.1)"

    read -rp "Server public IP [$detected_ip]: " server_ip
    server_ip="${server_ip:-$detected_ip}"

    read -rp "Mail hostname (e.g. mx.example.com): " mail_hostname

    read -rp "ACME email (Let's Encrypt): " acme_email

    read -rp "API port (not 8000) [8080]: " api_port
    api_port="${api_port:-8080}"

    read -rp "Admin username [admin]: " admin_user
    admin_user="${admin_user:-admin}"

    read -rsp "Admin password: " admin_password
    echo

    db_password="$(openssl rand -hex 24)"
    api_key="$(openssl rand -hex 32)"
    jwt_secret="$(openssl rand -hex 32)"

    cat > .env <<EOF
SERVER_IP=${server_ip}
MAIL_HOSTNAME=${mail_hostname}
ACME_EMAIL=${acme_email}
ACME_SERVER=https://acme-v02.api.letsencrypt.org/directory

API_PORT=${api_port}
API_KEY=${api_key}

ADMIN_USER=${admin_user}
ADMIN_PASSWORD=${admin_password}
JWT_SECRET=${jwt_secret}

POSTGRES_DB=mailservers
POSTGRES_USER=mailservers
POSTGRES_PASSWORD=${db_password}

DATABASE_URL=postgresql+psycopg://mailservers:${db_password}@postgres:5432/mailservers
EOF
    echo ".env created"
fi

docker compose build

docker compose up -d postgres api

echo "waiting for database..."
until docker compose exec -T postgres pg_isready -U mailservers -d mailservers >/dev/null 2>&1; do
    sleep 2
done

docker compose exec -T api python -m mailctl.bootstrap

docker compose up -d

api_port="$(grep '^API_PORT=' .env | cut -d= -f2)"
public_ip="$(grep '^SERVER_IP=' .env | cut -d= -f2)"

echo ""
echo "install done"
echo ""
echo "Open the Swagger UI to manage everything:"
echo "  http://${public_ip}:${api_port}/docs"
echo "Click Authorize and log in with your admin username and password."
