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
python manage.py load_exercises     # catalogue d'exercices ; sinon chargé à la première ouverture
make css                            # ou : tailwindcss -i assets/css/input.css -o core/static/core/css/app.css
python manage.py runserver   # port 5907 par défaut, DJANGO_PORT sinon
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

### Premier compte

À la toute première ouverture, l'application redirige vers `/bienvenue/` : aucun
utilisateur n'existe encore, et cet écran crée le compte initial, qui reçoit les
droits d'administration. Il disparaît définitivement une fois le compte créé.

En conteneur, `docker compose run --rm web python manage.py createsuperuser`
produit le même résultat en ligne de commande.

### Catalogue d'exercices

Le compte créé, l'application enchaîne sur `/exercices/chargement/` et importe
les 873 exercices livrés dans `src/exercises.json`. L'écran affiche l'avancement
et se referme définitivement une fois le catalogue en base.

Pour charger le catalogue sans passer par l'interface — déploiement automatisé,
installation sans navigateur — la commande est idempotente :

```bash
make exercises                                  # ou : python manage.py load_exercises
docker compose run --rm web python manage.py load_exercises
```

Ajouter `--force` pour réimporter un catalogue déjà chargé, après avoir
remplacé le fichier source. Celui-ci se déplace avec
`DJANGO_EXERCISES_SOURCE` si tu veux fournir ton propre référentiel ; les
illustrations vendorées suivent le même principe avec
`DJANGO_EXERCISES_IMAGES_SOURCE` (répertoire `<id>/0.jpg`, `<id>/1.jpg` par
exercice — voir `src/exercises/`).

Consignes en français et traduction unitaire : voir « Recharger le
référentiel » (Configuration → Admin, réservé au personnel) et le bouton
« Traduire cette fiche » sur une fiche non traduite — les deux dépendent d'un
fournisseur IA actif (`/settings/ai/`).

**Origine et licence.** Le catalogue (`src/exercises.json`) et ses
illustrations (`src/exercises/`) proviennent de
[`yuhonas/free-exercise-db`](https://github.com/yuhonas/free-exercise-db),
publié sous licence Unlicense (domaine public).

### Fournisseurs d'IA

1. Ouvrir **Fournisseurs IA** (`/settings/ai/`) — réservé aux administrateurs.
2. Enregistrer au moins un fournisseur. Chaque fiche renvoie directement vers la
   page où créer la clé (console Anthropic, Google AI Studio, console Mistral)
   ou, pour Ollama, vers la page d'installation.
3. Utiliser **Tester la connexion** pour valider les credentials avant de
   compter dessus.

Les clés saisies sont chiffrées avant d'atteindre la base et ne sont jamais
réaffichées : seul un masque de la forme `••••••••f3a9` apparaît.

---

## 6. Comptes utilisateurs

L'installation est **mono-utilisateur par défaut**, et prend en charge autant de
comptes que nécessaire. Chaque compte porte un identifiant, un mot de passe, une
adresse e-mail, un avatar, un sexe, une taille et un poids ; les mesures sont
facultatives et alimenteront le calibrage des programmes. Toute donnée
d'entraînement se rattachera à un utilisateur.

| Écran | Chemin | Accès |
|---|---|---|
| Premier compte | `/bienvenue/` | Public, tant qu'aucun compte n'existe |
| Mon profil | `/profil/` | Utilisateur connecté |
| Mot de passe | `/profil/mot-de-passe/` | Utilisateur connecté |
| Liste des comptes | `/comptes/` | Administrateurs |
| Créer / modifier | `/comptes/nouveau/`, `/comptes/<id>/` | Administrateurs |

**Désactiver plutôt que supprimer.** Un compte désactivé ne peut plus se
connecter mais conserve son historique. Un administrateur ne peut ni se
désactiver ni se retirer ses propres droits : l'installation resterait sans
administrateur.

**Inscription libre.** Désactivée par défaut. `DJANGO_ALLOW_SELF_REGISTRATION=True`
ouvre `/inscription/` et affiche le lien sur la page de connexion. Les comptes
ainsi créés sont ordinaires, jamais administrateurs.

**Avatars.** Stockés dans `MEDIA_ROOT` (`/app/media` en conteneur, monté sur le
volume `media_data`). Plafond par défaut : 2 Mo, ajustable via
`DJANGO_MAX_AVATAR_BYTES`. Django sert `/media/` lui-même, ce qui convient à une
installation auto-hébergée ; derrière un reverse proxy, faire servir ce chemin
directement par le proxy.

---

## 7. Connexion par SSO (OpenID Connect)

Facultatif et désactivé par défaut : tant que `OIDC_ENABLED` vaut `False`, aucune
route ni aucun bouton supplémentaire n'existe.

> ⚠️ **La connexion Google exige des identifiants OAuth.** Il n'existe pas de
> connexion « avec Gmail » sans clé : Google impose un *client ID* et un *client
> secret* créés dans Google Cloud Console pour toute application tierce. La
> procédure ci-dessous est le chemin le plus court pour y arriver.

### 7.1 Réglages communs

| Variable | Rôle |
|---|---|
| `OIDC_ENABLED` | Active l'intégration. Sans elle, tout le reste est ignoré. |
| `OIDC_PROVIDER_NAME` | Nom affiché sur le bouton (« Se connecter avec … ») |
| `OIDC_RP_CLIENT_ID` / `OIDC_RP_CLIENT_SECRET` | Identifiants délivrés par le fournisseur |
| `OIDC_OP_AUTHORIZATION_ENDPOINT` | URL d'autorisation |
| `OIDC_OP_TOKEN_ENDPOINT` | URL d'échange du jeton |
| `OIDC_OP_USER_ENDPOINT` | URL du profil (`userinfo`) |
| `OIDC_OP_JWKS_ENDPOINT` | Clés publiques — requis avec `RS256` |
| `OIDC_RP_SIGN_ALGO` | `RS256` par défaut |
| `OIDC_CREATE_USER` | `False` : seuls les comptes déjà créés peuvent se connecter |

**URL de rappel à déclarer chez le fournisseur :**

```
https://<votre-domaine>/oidc/callback/
```

En développement : `http://localhost:5907/oidc/callback/`.

**`OIDC_CREATE_USER`, le réglage qui compte.** Laissé à `False`, une personne
inconnue du fournisseur d'identité ne peut pas s'ouvrir un compte : il faut
l'avoir créée au préalable dans `/comptes/`, avec la même adresse e-mail. C'est
le réglage sûr lorsque le fournisseur n'est pas dédié à cette application —
avec Google, par exemple, `True` autoriserait n'importe quel compte Google du
monde à entrer.

### 7.2 Google

1. Ouvrir [Google Cloud Console](https://console.cloud.google.com/) et créer un
   projet (ou en réutiliser un).
2. **API et services → Écran de consentement OAuth** : renseigner le nom de
   l'application et l'e-mail d'assistance. Type *Externe* si les comptes ne sont
   pas dans un domaine Google Workspace.
3. **API et services → Identifiants → Créer des identifiants → ID client OAuth**,
   type *Application Web*.
4. Dans **URI de redirection autorisés**, ajouter
   `https://<votre-domaine>/oidc/callback/`.
5. Reporter l'identifiant et le secret obtenus dans `.env` :

```env
OIDC_ENABLED=True
OIDC_PROVIDER_NAME=Google
OIDC_RP_CLIENT_ID=xxxxxxxx.apps.googleusercontent.com
OIDC_RP_CLIENT_SECRET=xxxxxxxx
OIDC_RP_SIGN_ALGO=RS256
OIDC_OP_AUTHORIZATION_ENDPOINT=https://accounts.google.com/o/oauth2/v2/auth
OIDC_OP_TOKEN_ENDPOINT=https://oauth2.googleapis.com/token
OIDC_OP_USER_ENDPOINT=https://openidconnect.googleapis.com/v1/userinfo
OIDC_OP_JWKS_ENDPOINT=https://www.googleapis.com/oauth2/v3/certs
OIDC_CREATE_USER=False
```

6. Redémarrer l'application. Le bouton « Se connecter avec Google » apparaît sur
   la page de connexion.

### 7.3 Fournisseur générique (Keycloak, Authentik, Azure AD, Okta…)

Tout fournisseur OpenID Connect convient. Ses URL se lisent dans son document de
découverte, généralement à
`https://<fournisseur>/.well-known/openid-configuration` : y relever
`authorization_endpoint`, `token_endpoint`, `userinfo_endpoint` et `jwks_uri`.

Exemple avec Keycloak (realm `gym`) :

```env
OIDC_ENABLED=True
OIDC_PROVIDER_NAME=Keycloak
OIDC_RP_CLIENT_ID=ultimate-gym-generator
OIDC_RP_CLIENT_SECRET=xxxxxxxx
OIDC_OP_AUTHORIZATION_ENDPOINT=https://sso.exemple.fr/realms/gym/protocol/openid-connect/auth
OIDC_OP_TOKEN_ENDPOINT=https://sso.exemple.fr/realms/gym/protocol/openid-connect/token
OIDC_OP_USER_ENDPOINT=https://sso.exemple.fr/realms/gym/protocol/openid-connect/userinfo
OIDC_OP_JWKS_ENDPOINT=https://sso.exemple.fr/realms/gym/protocol/openid-connect/certs
OIDC_CREATE_USER=True
```

Le fournisseur étant ici dédié à l'organisation, `OIDC_CREATE_USER=True` est
raisonnable : toute personne qu'il authentifie a vocation à entrer.

### 7.4 Ce que le SSO renseigne, et ce qu'il ne touche pas

Le prénom, le nom et l'adresse e-mail proviennent du fournisseur et sont
rafraîchis à chaque connexion. Le sexe, la taille, le poids et l'avatar restent
la propriété de l'utilisateur : une reconnexion SSO ne les écrase jamais.

### 7.5 Diagnostic

| Symptôme | Piste |
|---|---|
| `redirect_uri_mismatch` | L'URI déclarée chez le fournisseur doit correspondre exactement, barre oblique finale comprise. |
| Retour sur la page de connexion sans message | `OIDC_CREATE_USER=False` et aucun compte local ne porte cette adresse e-mail. Créer le compte dans `/comptes/`. |
| Erreur de vérification de signature | `OIDC_OP_JWKS_ENDPOINT` absent alors que `OIDC_RP_SIGN_ALGO=RS256`. |
| Le bouton n'apparaît pas | `OIDC_ENABLED` n'est pas à `True`, ou l'application n'a pas été redémarrée. |
| `ImproperlyConfigured` au démarrage | `OIDC_ENABLED=True` mais une variable `OIDC_*` obligatoire est vide. |

---

## 8. Mise à jour

```bash
docker compose pull        # ou : git pull && docker compose build
docker compose up -d
```

Les migrations sont appliquées automatiquement au démarrage du conteneur. Si
une migration échoue, le conteneur s'arrête au lieu de servir une application
incohérente — consulter `docker compose logs web`.
