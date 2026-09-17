#!/usr/bin/env bash
# Met à jour et redémarre l'application sur un poste de déploiement (ex. Raspberry Pi).
#
# Étapes : récupère le code, installe les dépendances, force les réglages de
# production (DEBUG=False, WhiteNoise sert /static/ via le manifeste collecté),
# recompile le CSS, collecte les statiques, applique les migrations, puis
# relance `manage.py runserver` au premier plan.
#
# Usage : ./scripts/deploy.sh
# (à lancer depuis une session dédiée — tmux/screen — puisque le serveur
# tourne ensuite au premier plan ; Ctrl+C l'arrête).

set -euo pipefail

# --------------------------------------------------------------------------- #
# Configuration — ajuster au besoin selon l'installation du Pi.
# --------------------------------------------------------------------------- #

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIND_HOST="${DJANGO_BIND_HOST:-0.0.0.0}"
BIND_PORT="${DJANGO_PORT:-5907}"

cd "$PROJECT_DIR"

echo "==> Récupération du code (git pull)"
git pull

echo "==> Installation des dépendances de production"
# --break-system-packages : Raspberry Pi OS (Debian 12+) protège le Python
# système par défaut (PEP 668) ; pas de venv ici par choix du projet.
pip install --break-system-packages -r requirements/base.txt

# DEBUG=False et ALLOWED_HOSTS obligatoire sont vérifiés au chargement de
# config.settings.prod (ImproperlyConfigured sinon) — indispensable pour que
# WhiteNoise serve /static/ depuis le manifeste collecté plutôt que de
# retomber sur le mode développement de `runserver`.
export DJANGO_SETTINGS_MODULE=config.settings.prod

echo "==> Application des migrations"
python manage.py migrate

echo "==> Compilation du CSS (Tailwind)"
make css

echo "==> Collecte des fichiers statiques"
python manage.py collectstatic --noinput

echo "==> Démarrage du serveur sur ${BIND_HOST}:${BIND_PORT} (config.settings.prod)"
exec python manage.py runserver "${BIND_HOST}:${BIND_PORT}" --noreload
