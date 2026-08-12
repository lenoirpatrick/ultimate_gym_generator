#!/usr/bin/env bash
#
# Point d'entrée du conteneur : appliquer les migrations puis lancer le
# serveur. `set -e` garantit qu'un échec de migration arrête le conteneur
# plutôt que de servir une application incohérente.
set -euo pipefail

PORT="${DJANGO_PORT:-5907}"
WORKERS="${GUNICORN_WORKERS:-3}"
TIMEOUT="${GUNICORN_TIMEOUT:-60}"

# DJANGO_SECRET_KEY et CREDENTIALS_ENCRYPTION_KEY n'ont pas de valeur par défaut
# (config/settings/base.py, config/settings/prod.py) et sont indispensables au
# démarrage. Si l'une n'est pas fournie explicitement (.env, orchestrateur), on
# la génère au premier démarrage et on la persiste sur le volume de données
# (le même que la base : si ce volume disparaît, la base chiffrée qu'elle
# protège disparaît avec) pour qu'elle survive aux redémarrages et
# reconstructions d'image — la régénérer à chaque démarrage invaliderait
# sessions et liens signés, ou rendrait les credentials IA déjà enregistrés
# illisibles.
DATA_DIR="$(dirname "${DJANGO_DB_PATH:-/app/ugg_data/db.sqlite3}")"
mkdir -p "${DATA_DIR}"

generate_secret() {
    # $1 = nom de la variable d'environnement, $2 = fichier de persistance
    # (relatif à DATA_DIR), le reste = commande de génération.
    local var_name="$1" file_name="$2"
    shift 2
    if [ -n "${!var_name:-}" ]; then
        return
    fi
    local file="${DATA_DIR}/${file_name}"
    if [ ! -f "${file}" ]; then
        echo "[entrypoint] ${var_name} absente : génération et persistance dans ${file}."
        "$@" > "${file}"
        chmod 600 "${file}"
    fi
    export "${var_name}=$(cat "${file}")"
}

generate_secret DJANGO_SECRET_KEY secret_key \
    python -c "import secrets; print(secrets.token_urlsafe(64))"
generate_secret CREDENTIALS_ENCRYPTION_KEY credentials_key \
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

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
