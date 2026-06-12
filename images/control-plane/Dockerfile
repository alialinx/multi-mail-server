FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends docker.io openssl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY control-plane/pyproject.toml /app/pyproject.toml
COPY control-plane/mailctl /app/mailctl

RUN pip install --no-cache-dir .
