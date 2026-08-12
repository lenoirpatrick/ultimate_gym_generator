# Déploiement Docker

Le déploiement de référence se fait par conteneur. L'image embarque
l'application, ses dépendances Python compilées et les fichiers statiques
déjà collectés ; elle ne contient **aucun secret**.

---

## 1. Démarrage rapide avec `docker-compose`

```bash
cp .env.example .env
# Renseigner au minimum : DJANGO_SECRET_KEY, CREDENTIALS_ENCRYPTION_KEY,
# DJANGO_ALLOWED_HOSTS.

docker compose up -d --build
docker compose run --rm web python manage.py createsuperuser
```

L'application écoute sur <http://localhost:5907>.

Commandes utiles :

```bash
docker compose logs -f web        # suivre les journaux
docker compose ps                 # état des services et des healthchecks
docker compose down               # arrêter (les données restent sur l'hôte)
```

La base SQLite et les avatars vivent dans `./ugg_data` sur l'hôte (bind
mount, pas un volume Docker nommé) : `docker-compose.yml` monte
`./ugg_data:/app/ugg_data` (contient `db.sqlite3`) et
`./ugg_data/media:/app/media`. Ce dossier survit à `docker compose down`
comme à toute reconstruction de l'image — seule sa suppression manuelle
(`rm -rf ./ugg_data`) efface les données ⚠️. Voir [INSTALL.md](INSTALL.md)
pour le détail de `DJANGO_DB_PATH`.

---

## 2. Construction de l'image

Le `Dockerfile` est en deux étapes :

| Étape | Contenu |
|---|---|
| `builder` | Dépendances Python, build Tailwind, `collectstatic` |
| `runtime`  | Python, l'environnement virtuel et le code — utilisateur non-root `gym` (UID 10001) |

Les outils de compilation restent dans l'étape `builder` : l'image finale ne
les contient pas.

```bash
docker build -t plenoir/ultimate-gym-generator:latest .
```

Vérifier l'image avant publication :

```bash
docker image inspect plenoir/ultimate-gym-generator:latest --format '{{.Config.User}}'   # → gym
docker run --rm plenoir/ultimate-gym-generator:latest python -c "import django; print(django.get_version())"
```

---

## 3. Publication sur Docker Hub

### Préparation (une seule fois)

1. Créer le dépôt `plenoir/ultimate-gym-generator` sur
   [hub.docker.com](https://hub.docker.com/).
2. Générer un **jeton d'accès** (Account Settings → Personal access tokens) —
   ne jamais utiliser le mot de passe du compte.
3. Enregistrer ce jeton dans les secrets GitHub du dépôt sous
   `DOCKERHUB_TOKEN`, et l'identifiant sous `DOCKERHUB_USERNAME`.

### Publication manuelle

```bash
# 1. Authentification (le jeton est lu sur l'entrée standard, pas dans l'historique shell)
echo "$DOCKERHUB_TOKEN" | docker login --username plenoir --password-stdin

# 2. Construction multi-architecture et envoi en une seule étape
# --platform : sans ça, l'image ne cible que l'architecture de la machine qui
# construit — inutilisable sur un Raspberry Pi (linux/arm64) si elle vient
# d'un poste linux/amd64 (« exec format error » au démarrage).
# --provenance=false --sbom=false : sans ça, un manifest list d'attestations
# s'ajoute et certains clients échouent à le lire (« does not provide any
# platform »). --push est obligatoire ici : une image multi-plateforme ne
# peut pas être chargée dans le moteur Docker local (pas de --load possible),
# seulement poussée directement vers le registre.
VERSION=0.1.0
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --provenance=false --sbom=false \
  --push \
  -t plenoir/ultimate-gym-generator:$VERSION \
  -t plenoir/ultimate-gym-generator:latest \
  .

# 3. Déconnexion (le jeton reste sinon en clair dans ~/.docker/config.json)
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
- **`DJANGO_SECRET_KEY` et `CREDENTIALS_ENCRYPTION_KEY` peuvent rester vides** :
  `docker/entrypoint.sh` en génère une pour chacune au premier démarrage si
  elle est absente, et la persiste dans `<dossier de DJANGO_DB_PATH>/secret_key`
  et `.../credentials_key`, sur le même volume que la base — elles survivent
  donc aux redémarrages et reconstructions d'image, tant que le volume
  `ugg_data` n'est pas supprimé (`docker compose down -v`). Perdre ce volume
  perd la base chiffrée en même temps que la clé qui la protège, donc pas de
  credentials orphelins illisibles. Les renseigner explicitement dans `.env`
  reste nécessaire si plusieurs environnements doivent partager les mêmes
  clés (sessions/jetons ou credentials valables des deux côtés).
- **`DJANGO_DB_PATH` a aussi un défaut prêt à l'emploi** : `/app/ugg_data/db.sqlite3`,
  baké dans l'image (Dockerfile) et repris explicitement par
  `docker-compose.yml`. Un `docker run` sans docker-compose fonctionne donc
  sans variable supplémentaire, à condition de monter un volume sur
  `/app/ugg_data` (sinon Docker en crée un anonyme, perdu au prochain `docker
  run` — voir la table de diagnostic).
- **Bind mount et utilisateur non-root (hôte Linux) :** si `./ugg_data`
  n'existe pas encore, Docker le crée appartenant à `root`, inaccessible en
  écriture à `gym` (UID 10001) qui exécute le conteneur — voir la table de
  diagnostic. Sur Docker Desktop (Windows/macOS), la couche de partage de
  fichiers n'applique pas cette contrainte d'UID.
- Le conteneur tourne en **non-root** (`gym`, UID 10001).
- Le `HEALTHCHECK` interroge `/healthz`, qui vérifie aussi l'accès à la base :
  un conteneur qui répond sans base est signalé `unhealthy`.

---

## 5. Diagnostic

| Symptôme | Piste |
|---|---|
| `exec /app/docker/entrypoint.sh: no such file` | Fins de ligne CRLF. `.gitattributes` force LF ; vérifier avec `file docker/entrypoint.sh`. |
| `ImproperlyConfigured: Set the DJANGO_SECRET_KEY environment variable` ou `CREDENTIALS_ENCRYPTION_KEY est obligatoire` | Ne devrait plus se produire via `docker compose up` (génération automatique par `docker/entrypoint.sh`, voir « Règles de sécurité » ci-dessus). Si l'erreur persiste : le conteneur est lancé autrement que par l'entrypoint (`docker run --entrypoint …`), ou `DJANGO_DB_PATH` pointe vers un dossier non accessible en écriture par `gym`. |
| `ImproperlyConfigured: DJANGO_DB_PATH` | Variable explicitement vidée (`DJANGO_DB_PATH=` dans `.env` ou l'environnement) : l'image fournit un défaut, ce message n'apparaît que si quelque chose l'écrase par une valeur vide. |
| Base réinitialisée à chaque `docker run` (hors compose) | Aucun volume monté sur `/app/ugg_data` : Docker en crée un anonyme à chaque nouveau conteneur. Monter un dossier hôte explicitement (`-v $(pwd)/ugg_data:/app/ugg_data`), ou passer par `docker-compose.yml` qui le fait déjà. |
| `PermissionError` / `sqlite3.OperationalError: unable to open database file` (hôte Linux) | `./ugg_data` appartient à `root` (créé par Docker au premier montage). Corriger une fois : `sudo mkdir -p ./ugg_data/media && sudo chown -R 10001:10001 ./ugg_data`. |
| Toute requête reçoit un `301` et n'aboutit jamais (navigateur ou `HEALTHCHECK`, conteneur `unhealthy`) | `SECURE_SSL_REDIRECT` (vrai par défaut en production) redirige vers `https://`, absent de cette pile. `docker-compose.yml` le force déjà à `False` ; vérifier qu'il n'a pas été retiré du service `web`. À ne repasser à `True` que derrière un reverse proxy TLS transmettant `X-Forwarded-Proto`. |
| `DisallowedHost` | Ajouter le nom d'hôte à `DJANGO_ALLOWED_HOSTS`. |
| CSRF refusé derrière un proxy | Renseigner `DJANGO_CSRF_TRUSTED_ORIGINS` avec le schéma (`https://…`). |
| Statiques absents | L'image les collecte au build : reconstruire sans cache (`docker build --no-cache`). |
