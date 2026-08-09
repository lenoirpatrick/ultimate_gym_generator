#!/usr/bin/env bash
#
# Point d'entrée du conteneur : attendre la base, appliquer les migrations,
# puis lancer le serveur. `set -e` garantit qu'un échec de migration arrête
# le conteneur plutôt que de servir une application incohérente.
set -euo pipefail

PORT="${DJANGO_PORT:-5907}"
WORKERS="${GUNICORN_WORKERS:-3}"
TIMEOUT="${GUNICORN_TIMEOUT:-60}"
DB_WAIT_SECONDS="${DB_WAIT_SECONDS:-60}"

echo "[entrypoint] Attente de la base de données (${DB_WAIT_SECONDS}s maximum)…"
python - "$DB_WAIT_SECONDS" <<'PYTHON'
import sys
import time

import django
from django.db import connections
from django.db.utils import OperationalError

django.setup()

deadline = time.monotonic() + float(sys.argv[1])
while True:
    try:
        connections["default"].cursor().close()
        print("[entrypoint] Base joignable.")
        break
    except OperationalError as exc:
        if time.monotonic() >= deadline:
            sys.exit(f"[entrypoint] Base injoignable : {exc}")
        time.sleep(1)
PYTHON

echo "[entrypoint] Application des migrations…"
python manage.py migrate --noinput

case "${1:-gunicorn}" in
    gunicorn)
        echo "[entrypoint] Démarrage de Gunicorn sur le port ${PORT}."
        exec gunicorn config.wsgi:application \
            --bind "0.0.0.0:${PORT}" \
            --workers "${WORKERS}" \
            --timeout "${TIMEOUT}" \
            --access-logfile - \
            --error-logfile -
        ;;
    *)
        # Permet `docker compose run web python manage.py createsuperuser`.
        exec "$@"
        ;;
esac
