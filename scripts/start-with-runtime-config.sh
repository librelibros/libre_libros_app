#!/bin/sh
set -eu

RUNTIME_CONFIG_PATH="${LIBRE_LIBROS_RUNTIME_CONFIG_PATH:-}"
WAIT_FOR_RUNTIME_CONFIG="${LIBRE_LIBROS_WAIT_FOR_RUNTIME_CONFIG:-false}"

if [ -n "$RUNTIME_CONFIG_PATH" ] && [ "$WAIT_FOR_RUNTIME_CONFIG" = "true" ]; then
  COUNT=0
  while [ ! -f "$RUNTIME_CONFIG_PATH" ] && [ "$COUNT" -lt 120 ]; do
    COUNT=$((COUNT + 1))
    sleep 2
  done
fi

if [ -n "$RUNTIME_CONFIG_PATH" ] && [ -f "$RUNTIME_CONFIG_PATH" ]; then
  set -a
  . "$RUNTIME_CONFIG_PATH"
  set +a
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
