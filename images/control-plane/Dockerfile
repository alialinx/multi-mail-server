FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends openssl curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-27.5.1.tgz \
    | tar -xz -C /usr/local/bin --strip-components=1 docker/docker

WORKDIR /app

COPY control-plane/pyproject.toml /app/pyproject.toml
COPY control-plane/mailctl /app/mailctl

RUN pip install --no-cache-dir .
