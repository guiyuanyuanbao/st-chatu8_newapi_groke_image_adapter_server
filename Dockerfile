FROM python:3.12-slim

WORKDIR /app

COPY relay_server.py /app/relay_server.py
COPY docker-entrypoint.sh /app/docker-entrypoint.sh

RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 3100

ENTRYPOINT ["/app/docker-entrypoint.sh"]
