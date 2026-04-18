#!/bin/sh
set -eu

LISTEN_HOST="${LISTEN_HOST:-0.0.0.0}"
LISTEN_PORT="${LISTEN_PORT:-3100}"
UPSTREAM_SCHEME="${UPSTREAM_SCHEME:-http}"
UPSTREAM_TIMEOUT="${UPSTREAM_TIMEOUT:-60}"

if [ -z "${UPSTREAM_HOST:-}" ]; then
  echo "UPSTREAM_HOST is required" >&2
  exit 1
fi

if [ -z "${UPSTREAM_PORT:-}" ]; then
  echo "UPSTREAM_PORT is required" >&2
  exit 1
fi

exec python /app/relay_server.py \
  --listen-host "${LISTEN_HOST}" \
  --listen-port "${LISTEN_PORT}" \
  --upstream-host "${UPSTREAM_HOST}" \
  --upstream-port "${UPSTREAM_PORT}" \
  --upstream-scheme "${UPSTREAM_SCHEME}" \
  --timeout "${UPSTREAM_TIMEOUT}"
