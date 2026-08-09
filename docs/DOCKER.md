# Déploiement Docker

Le déploiement de référence se fait par conteneur. L'image embarque
l'application, ses dépendances Python compilées et les fichiers statiques
déjà collectés ; elle ne contient **aucun secret**.

---

## 1. Démarrage rapide avec `docker-compose`

```bash
cp .env.example .env
# Renseigner au minimum : DJANGO_SECRET_KEY, CREDENTIALS_ENCRYPTION_KEY,
# DB_PASSWORD, MARIADB_ROOT_PASSWORD, DJANGO_ALLOWED_HOSTS.

docker compose up -d --build
docker compose run --rm web python manage.py createsuperuser
```

L'application écoute sur <http://localhost:5907>.

Commandes utiles :

```bash
docker compose logs -f web        # suivre les journaux
docker compose ps                 # état des services et des healthchecks
docker compose down               # arrêter (les volumes sont conservés)
docker compose down -v            # arrêter ET supprimer les données ⚠️
```

### Utiliser une MariaDB externe

1. Commenter l'intégralité du service `db` dans `docker-compose.yml`.
2. Commenter le bloc `depends_on` du service `web`.
3. Renseigner `DATABASE_URL` dans `.env` :
   `mysql://utilisateur:motdepasse@hote:3306/nom_de_base`

Aucune modification de code n'est nécessaire. Les points de configuration
détaillés (jeu de caractères, droits, TLS) sont dans [INSTALL.md](INSTALL.md).

---

## 2. Construction de l'image

Le `Dockerfile` est en deux étapes :

| Étape | Contenu |
|---|---|
| `builder` | `build-essential`, en-têtes MariaDB, compilation de `mysqlclient`, build Tailwind, `collectstatic` |
| `runtime`  | Python, `libmariadb3`, l'environnement virtuel et le code — utilisateur non-root `gym` (UID 10001) |

Les outils de compilation restent dans l'étape `builder` : l'image finale ne
les contient pas.

```bash
docker build -t lenoirpatrick/ultimate-gym-generator:latest .
```

Vérifier l'image avant publication :

```bash
docker image inspect lenoirpatrick/ultimate-gym-generator:latest --format '{{.Config.User}}'   # → gym
docker run --rm lenoirpatrick/ultimate-gym-generator:latest python -c "import django; print(django.get_version())"
```

---

## 3. Publication sur Docker Hub

### Préparation (une seule fois)

1. Créer le dépôt `lenoirpatrick/ultimate-gym-generator` sur
   [hub.docker.com](https://hub.docker.com/).
2. Générer un **jeton d'accès** (Account Settings → Personal access tokens) —
   ne jamais utiliser le mot de passe du compte.
3. Enregistrer ce jeton dans les secrets GitHub du dépôt sous
   `DOCKERHUB_TOKEN`, et l'identifiant sous `DOCKERHUB_USERNAME`.

### Publication manuelle

```bash
# 1. Authentification (le jeton est lu sur l'entrée standard, pas dans l'historique shell)
echo "$DOCKERHUB_TOKEN" | docker login --username lenoirpatrick --password-stdin

# 2. Construction et double étiquetage
VERSION=0.1.0
docker build \
  -t lenoirpatrick/ultimate-gym-generator:$VERSION \
  -t lenoirpatrick/ultimate-gym-generator:latest \
  .

# 3. Envoi
docker push lenoirpatrick/ultimate-gym-generator:$VERSION
docker push lenoirpatrick/ultimate-gym-generator:latest

# 4. Déconnexion (le jeton reste sinon en clair dans ~/.docker/config.json)
docker logout
```

### Publication automatique

Le workflow `.github/workflows/release.yml` construit et publie l'image
multi-architecture (`linux/amd64`, `linux/arm64`) à chaque étiquette `v*` :

```bash
git tag -a v0.1.0 -m "Première version"
git push origin v0.1.0
```

### Convention d'étiquetage

| Étiquette | Signification |
|---|---|
| `latest` | Dernière version stable publiée |
| `X.Y.Z`  | Version précise, immuable — à utiliser en production |
| `sha-<court>` | Commit exact, produit par la CI pour le diagnostic |

En production, épingler une version précise plutôt que `latest` : un `docker
compose pull` ne doit jamais changer de version applicative par surprise.

---

## 4. Règles de sécurité

- **Aucun secret dans l'image.** Tout passe par des variables d'environnement
  au démarrage. `.env` est exclu par `.dockerignore` et par `.gitignore`.
- **Aucun secret en argument de build.** Un `ARG` reste lisible dans les
  couches de l'image via `docker history`.
- Le conteneur tourne en **non-root** (`gym`, UID 10001).
- Le port de la base n'est pas publié par défaut.
- Le `HEALTHCHECK` interroge `/healthz`, qui vérifie aussi l'accès à la base :
  un conteneur qui répond sans base est signalé `unhealthy`.

---

## 5. Diagnostic

| Symptôme | Piste |
|---|---|
| `exec /app/docker/entrypoint.sh: no such file` | Fins de ligne CRLF. `.gitattributes` force LF ; vérifier avec `file docker/entrypoint.sh`. |
| Le conteneur s'arrête sur `Base injoignable` | La base n'a pas démarré dans le délai imparti. Augmenter `DB_WAIT_SECONDS`, ou vérifier `DB_HOST` / `DATABASE_URL`. |
| `ImproperlyConfigured: CREDENTIALS_ENCRYPTION_KEY` | Variable absente du `.env`. La générer (voir `.env.example`). |
| `DisallowedHost` | Ajouter le nom d'hôte à `DJANGO_ALLOWED_HOSTS`. |
| CSRF refusé derrière un proxy | Renseigner `DJANGO_CSRF_TRUSTED_ORIGINS` avec le schéma (`https://…`). |
| Statiques absents | L'image les collecte au build : reconstruire sans cache (`docker build --no-cache`). |
