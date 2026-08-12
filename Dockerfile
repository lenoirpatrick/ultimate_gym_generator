# syntax=docker/dockerfile:1

# =============================================================================
# Étape 1 — construction : dépendances + feuille de style + statiques.
# =============================================================================
FROM python:3.14-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Couche de dépendances séparée : le cache survit à toute modification du code.
COPY requirements/ /tmp/requirements/
RUN pip install --upgrade pip && pip install -r /tmp/requirements/base.txt

WORKDIR /app
COPY . .

# Feuille de style Tailwind. `pytailwindcss` récupère le binaire autonome —
# aucune dépendance Node dans le projet ni dans l'image.
RUN pip install pytailwindcss \
    && tailwindcss -i assets/css/input.css -o core/static/core/css/app.css --minify

# Collecte des statiques. Aucun secret réel n'est nécessaire ni injecté :
# ces valeurs de façade servent uniquement à instancier les settings.
RUN DJANGO_SETTINGS_MODULE=config.settings.dev \
    DJANGO_DEBUG=False \
    DJANGO_SECRET_KEY=collectstatic-uniquement \
    python manage.py collectstatic --noinput --clear

# =============================================================================
# Étape 2 — exécution : Python et le code, rien de plus.
# =============================================================================
FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod \
    DJANGO_PORT=5907 \
    PATH="/opt/venv/bin:$PATH"

RUN useradd --create-home --uid 10001 gym

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --from=builder --chown=gym:gym /app /app

RUN chmod +x /app/docker/entrypoint.sh \
    # Points de montage des avatars et de la base SQLite : créés et attribués
    # avant de perdre les droits root, sinon un volume monté ici serait
    # inaccessible en écriture.
    && mkdir -p /app/media /app/data && chown gym:gym /app/media /app/data

USER gym

VOLUME ["/app/media", "/app/data"]

# 5907 = « sport » en leet.
EXPOSE 5907

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import os,sys,urllib.request; \
url='http://127.0.0.1:%s/healthz' % os.environ.get('DJANGO_PORT','5907'); \
sys.exit(0 if urllib.request.urlopen(url, timeout=4).status == 200 else 1)"

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["gunicorn"]
