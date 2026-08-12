#!/usr/bin/env bash
#
# Point d'entrée du conteneur : appliquer les migrations puis lancer le
# serveur. `set -e` garantit qu'un échec de migration arrête le conteneur
# plutôt que de servir une application incohérente.
set -euo pipefail

PORT="${DJANGO_PORT:-5907}"
WORKERS="${GUNICORN_WORKERS:-3}"
TIMEOUT="${GUNICORN_TIMEOUT:-60}"

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
