#!/usr/bin/env sh
# Waits for the database, applies migrations, then hands over to the real
# command via exec so that PID 1 is the server and signals reach it directly.
set -eu

if [ "${DJANGO_WAIT_FOR_DB:-true}" = "true" ] && [ -n "${DATABASE_URL:-}" ]; then
    echo "waiting for the database..."
    python - <<'PY'
import os
import sys
import time
from urllib.parse import urlparse
import socket

url = urlparse(os.environ["DATABASE_URL"])
host, port = url.hostname, url.port or 5432
deadline = time.time() + float(os.environ.get("DJANGO_WAIT_FOR_DB_TIMEOUT", "60"))

while time.time() < deadline:
    try:
        with socket.create_connection((host, port), timeout=2):
            print(f"database reachable at {host}:{port}")
            sys.exit(0)
    except OSError:
        time.sleep(1)

print(f"database at {host}:{port} not reachable in time", file=sys.stderr)
sys.exit(1)
PY
fi

if [ "${DJANGO_MIGRATE_ON_START:-true}" = "true" ]; then
    # Fine for a single-service deployment. With several replicas starting at
    # once, turn this off and run migrations as a separate step in the deploy,
    # or two replicas will race each other applying the same migration.
    echo "applying migrations..."
    python manage.py migrate --noinput
fi

exec "$@"
