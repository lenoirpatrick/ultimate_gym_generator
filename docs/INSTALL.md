# Installation

Deux chemins : **Docker** (recommandé, tout est fourni) ou **installation
locale** pour développer.

L'application écoute sur le port **5907** (« sport » en leet) dans les deux cas.

---

## 1. Variables de configuration

Toute la configuration passe par l'environnement. Partir de `.env.example`,
qui documente chaque variable.

### Obligatoires

| Variable | Rôle |
|---|---|
| `DJANGO_SECRET_KEY` | Signature des sessions et des jetons CSRF. `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `CREDENTIALS_ENCRYPTION_KEY` | Chiffre les clés d'API stockées en base. `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `DJANGO_ALLOWED_HOSTS` | Noms d'hôte servis. Obligatoire en production. |

> ⚠️ **`CREDENTIALS_ENCRYPTION_KEY` est à sauvegarder hors de la base.** La
> perdre rend illisibles tous les credentials IA déjà enregistrés : il faudra
> les ressaisir. La changer produit le même effet.

### Principales variables facultatives

| Variable | Défaut | Rôle |
|---|---|---|
| `DJANGO_DEBUG` | `False` | `True` en développement uniquement |
| `DJANGO_PORT` | `5907` | Port d'écoute |
| `DJANGO_ADMIN_URL` | `admin/` | Déplaçable pour réduire la surface d'attaque |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | vide | Requis derrière un reverse proxy HTTPS |
| `DJANGO_TIME_ZONE` | `Europe/Paris` | |
| `GUNICORN_WORKERS` | `3` | Processus applicatifs (conteneur) |
| `DB_WAIT_SECONDS` | `60` | Attente maximale de la base au démarrage (conteneur) |

---

## 2. Base de données

L'application résout sa base dans cet ordre, sans changement de code :

1. **`DATABASE_URL`** si renseignée — a priorité sur tout le reste.
2. **`DB_HOST` + `DB_*`** sinon — le cas du `docker-compose` fourni.
3. **SQLite** si ni l'une ni l'autre — repli de développement local.
   `config.settings.prod` refuse ce cas et arrête le démarrage.

### MariaDB fournie par docker-compose

Rien à faire : le service `db` du `docker-compose.yml` est créé avec les
valeurs `DB_*` du `.env`. Laisser `DATABASE_URL` vide.

### MariaDB externe

Renseigner `DATABASE_URL` :

```
DATABASE_URL=mysql://utilisateur:motdepasse@bdd.exemple.fr:3306/gym
```

puis commenter le service `db` et le bloc `depends_on` dans
`docker-compose.yml`.

**Points de configuration à vérifier côté serveur MariaDB :**

| Point | Valeur attendue |
|---|---|
| Version | MariaDB 10.6 ou supérieure (11.4 LTS recommandée) |
| Jeu de caractères | `utf8mb4` / `utf8mb4_unicode_ci` — indispensable pour les accents et les emojis |
| Base | Créée au préalable ; l'application ne crée pas sa base |
| Droits | `SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, DROP, REFERENCES` sur cette base |
| Réseau | Le serveur doit accepter les connexions depuis l'hôte applicatif |
| Fuseau horaire | Tables de fuseaux chargées, ou serveur en UTC |

Préparation type :

```sql
CREATE DATABASE gym CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'gym'@'%' IDENTIFIED BY 'un-mot-de-passe-solide';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, DROP, REFERENCES
    ON gym.* TO 'gym'@'%';
FLUSH PRIVILEGES;
```

**Connexion chiffrée (TLS).** Ajouter les paramètres à l'URL, par exemple
`?ssl-ca=/chemin/ca.pem`. Le fichier doit être accessible depuis le conteneur
(le monter en volume).

**Base gérée (RDS, Scaleway, OVH…)** : renseigner `DATABASE_URL` avec le point
de terminaison fourni. Vérifier que le groupe de sécurité autorise l'hôte
applicatif et que le jeu de caractères par défaut est bien `utf8mb4`.

---

## 3. Installation par conteneur

Voir [DOCKER.md](DOCKER.md) pour la procédure complète, la construction de
l'image et la publication sur Docker Hub. En résumé :

```bash
cp .env.example .env      # puis renseigner les variables obligatoires
docker compose up -d --build
docker compose run --rm web python manage.py createsuperuser
```

---

## 4. Installation locale (développement)

Prérequis : Python 3.13 ou 3.14.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate

pip install -r requirements/dev.txt

cp .env.example .env
# Générer DJANGO_SECRET_KEY et CREDENTIALS_ENCRYPTION_KEY,
# puis vider DB_HOST pour utiliser SQLite.

python manage.py migrate
python manage.py createsuperuser
make css                            # ou : tailwindcss -i assets/css/input.css -o core/static/core/css/app.css
python manage.py runserver 5907
```

> Sur Windows, `mysqlclient` s'installe depuis une roue précompilée. En cas
> d'échec de compilation, installer les outils de build Visual C++ — ou rester
> sur SQLite en développement, la dépendance n'étant nécessaire que pour
> MariaDB.

Pendant le développement du CSS, `make css-watch` recompile à chaque
modification de gabarit.

### Vérifications

```bash
make test        # pytest + couverture
make lint        # ruff check + ruff format --check
make check       # python manage.py check --deploy
```

---

## 5. Après l'installation

1. Se connecter avec le compte administrateur créé.
2. Ouvrir **Fournisseurs IA** (`/settings/ai/`) et enregistrer au moins un
   fournisseur (Anthropic, Gemini, Mistral ou Ollama).
3. Utiliser **Tester la connexion** pour valider les credentials avant de
   compter dessus.

Les clés saisies sont chiffrées avant d'atteindre la base et ne sont jamais
réaffichées : seul un masque de la forme `••••••••f3a9` apparaît.

---

## 6. Mise à jour

```bash
docker compose pull        # ou : git pull && docker compose build
docker compose up -d
```

Les migrations sont appliquées automatiquement au démarrage du conteneur. Si
une migration échoue, le conteneur s'arrête au lieu de servir une application
incohérente — consulter `docker compose logs web`.
