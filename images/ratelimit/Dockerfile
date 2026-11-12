FROM python:3.12-slim

COPY ratelimit.py /app/ratelimit.py

EXPOSE 10040
USER nobody
ENTRYPOINT ["python", "-u", "/app/ratelimit.py"]
