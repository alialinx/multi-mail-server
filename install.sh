#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

TOTAL=6

step() {
    echo ""
    echo "==> Step $1/$TOTAL ($(( $1 * 100 / TOTAL ))%) - $2"
}

step 1 "Checking Docker"
if ! command -v docker >/dev/null 2>&1; then
    echo "    Docker not found. Installing, this can take a minute..."
    if curl -fsSL https://get.docker.com | sh >/tmp/docker-install.log 2>&1; then
        echo "    Docker installed."
    else
        echo "    Docker install failed. See /tmp/docker-install.log"
        exit 1
    fi
else
    echo "    Docker is already installed."
fi

if ! docker compose version >/dev/null 2>&1; then
    echo "    docker compose plugin is missing. Install it and run again."
    exit 1
fi

step 2 "Creating configuration"
if [ ! -f .env ]; then
    detected_ip="$(curl -fsS https://api.ipify.org || echo 127.0.0.1)"

    read -rp "    Server public IP [$detected_ip]: " server_ip
    server_ip="${server_ip:-$detected_ip}"

    while :; do
        read -rp "    Mail hostname (e.g. mx.example.com): " mail_hostname
        # strip stray/control/non-ascii bytes that a bad paste can introduce
        mail_hostname=$(printf '%s' "$mail_hostname" | tr -cd 'a-zA-Z0-9.-')
        if printf '%s' "$mail_hostname" | grep -qE '^([a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'; then
            break
        fi
        echo "    Please enter a valid hostname like mx.example.com."
    done

    read -rp "    ACME email (Let's Encrypt): " acme_email

    read -rp "    API port (not 8000) [8080]: " api_port
    api_port="${api_port:-8080}"

    read -rp "    Web panel port [3000]: " web_port
    web_port="${web_port:-3000}"

    read -rp "    Admin username [admin]: " admin_user
    admin_user="${admin_user:-admin}"

    read -rsp "    Admin password: " admin_password
    echo

    db_password="$(openssl rand -hex 24)"
    jwt_secret="$(openssl rand -hex 32)"

    cat > .env <<EOF
SERVER_IP=${server_ip}
MAIL_HOSTNAME=${mail_hostname}
ACME_EMAIL=${acme_email}
ACME_SERVER=https://acme-v02.api.letsencrypt.org/directory

API_PORT=${api_port}
WEB_PORT=${web_port}

ADMIN_USER=${admin_user}
ADMIN_PASSWORD=${admin_password}
JWT_SECRET=${jwt_secret}

POSTGRES_DB=mailservers
POSTGRES_USER=mailservers
POSTGRES_PASSWORD=${db_password}

DATABASE_URL=postgresql+psycopg://mailservers:${db_password}@postgres:5432/mailservers
EOF
    echo "    Settings saved to .env"
else
    echo "    .env already exists, keeping it."
fi

step 3 "Building images (first run can take a few minutes)"
docker compose build

step 4 "Starting database"
docker compose up -d postgres api
echo "    Waiting for the database..."
until docker compose exec -T postgres pg_isready -U mailservers -d mailservers >/dev/null 2>&1; do
    sleep 2
done
echo "    Database is ready."

step 5 "Setting up database and base config"
docker compose exec -T api python -m mailctl.bootstrap

step 6 "Starting all services"
docker compose up -d

api_port="$(grep '^API_PORT=' .env | cut -d= -f2)"
web_port="$(grep '^WEB_PORT=' .env | cut -d= -f2)"
public_ip="$(grep '^SERVER_IP=' .env | cut -d= -f2)"

echo ""
echo "============================================================"
echo " Install complete."
echo ""
echo " Web panel (recommended):"
echo "   http://${public_ip}:${web_port}/"
echo " Swagger UI (raw API):"
echo "   http://${public_ip}:${api_port}/docs"
echo ""
echo " Log in with your admin username and password."
echo " Open only the web and API ports to your own IP in the firewall."
echo "============================================================"
