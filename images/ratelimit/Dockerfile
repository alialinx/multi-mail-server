FROM python:3.12-slim

COPY ratelimit.py /app/ratelimit.py
RUN mkdir -p /data && chown nobody:nogroup /data

EXPOSE 10040 10041
USER nobody
ENTRYPOINT ["python", "-u", "/app/ratelimit.py"]
