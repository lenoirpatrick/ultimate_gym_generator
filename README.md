# Ultimate Gym Generator

Générateur de programmes d'entraînement assisté par IA. Application Django
servie sur le port **5907** (« sport » en leet).

À ce stade, les fondations sont posées — configuration, base de données,
authentification, credentials IA, catalogue d'exercices, socle visuel et
minuteur de suivi de séance. La génération de programmes n'est pas encore
implémentée.

## Pile technique

| Rôle | Choix |
|---|---|
| Runtime | Python 3.13+ · Django 6.1 |
| Base | SQLite, fichier persisté sur volume en conteneur |
| Interface | Gabarits Django + HTMX 2 (vendoré) + Tailwind CSS 4 (CLI autonome, zéro Node) |
| Fournisseurs IA | Anthropic (SDK officiel), Gemini / Mistral / Ollama (REST via httpx) |
| Comptes | Mono-utilisateur par défaut, multi-utilisateurs pris en charge ; SSO OpenID Connect facultatif |
| Serveur | Gunicorn + WhiteNoise, conteneur non-root |

## Démarrage rapide

Deux chemins : **Docker** (recommandé) ou installation locale pour développer.

```bash
cp .env.example .env
# Renseigner au minimum : DJANGO_SECRET_KEY, CREDENTIALS_ENCRYPTION_KEY,
# DJANGO_ALLOWED_HOSTS.

docker compose up -d --build
docker compose run --rm web python manage.py createsuperuser
```

L'application écoute sur <http://localhost:5907>.

- Installation locale détaillée, variables de configuration : [`docs/INSTALL.md`](docs/INSTALL.md)
- Déploiement et exploitation du conteneur : [`docs/DOCKER.md`](docs/DOCKER.md)

## Commandes de développement

```bash
make install      # dépendances de développement
make css          # compile assets/css → core/static/core/css/app.css
make run          # serveur de développement sur le port 5907
make migrate      # applique les migrations
make superuser    # crée un compte administrateur
make exercises    # charge le catalogue d'exercices (idempotent)
make test         # pytest + couverture
make lint         # ruff check + ruff format --check
```

`make help` liste les cibles disponibles.

## Contribuer

Conventions de code, règles graphiques et posture attendue : voir
[`CLAUDE.md`](CLAUDE.md) — document vivant tenu à jour à chaque décision
visuelle ou technique.

## Licences

Le catalogue d'exercices vendoré (`src/exercises.json` et ses illustrations)
provient de [free-exercise-db](https://github.com/yuhonas/free-exercise-db)
(licence Unlicense).
