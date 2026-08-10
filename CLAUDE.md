# CLAUDE.md — Manifeste du projet

## Projet

**ultimate_gym_generator** — générateur de programmes d'entraînement assisté par IA.
Application Django servie sur le port **5907** (« sport » en leet).

À ce stade, seules les fondations sont posées : configuration, base de données,
authentification, credentials IA, catalogue d'exercices et socle visuel. La
génération de programmes n'est pas encore implémentée.

| Rôle | Choix |
|---|---|
| Runtime | Python 3.13+ · Django 6.1 |
| Base | MariaDB 11 (`mysqlclient`), interne ou externe via `DATABASE_URL` ; SQLite en repli local |
| Configuration | `django-environ`, tout par variables d'environnement |
| Interface | Gabarits Django + HTMX 2 (vendoré) + Tailwind CSS 4 (CLI autonome, zéro Node) |
| Chiffrement | Fernet (`cryptography`) pour les clés d'API en base |
| Fournisseurs IA | Anthropic (SDK officiel), Gemini / Mistral / Ollama (REST via httpx) |
| Comptes | Mono-utilisateur par défaut, multi-utilisateurs pris en charge ; SSO OpenID Connect facultatif (`mozilla-django-oidc`) |
| Serveur | Gunicorn + WhiteNoise, conteneur non-root |
| Qualité | `ruff`, `pytest` + `pytest-django` + couverture, SonarCloud |

```
assets/css/       tokens.css (SOURCE DE VÉRITÉ graphique), components.css, input.css
config/settings/  base · dev · test · prod
accounts/         utilisateur (avatar, mesures), authentification, SSO, gestion des comptes
aiproviders/      credentials chiffrés, registre des fournisseurs, adaptateurs, /settings/ai/
exercises/        catalogue d'exercices, import par lots, écran de chargement
core/             gabarit de base, composants, spinners, /healthz, /style-guide/
docker/           entrypoint du conteneur
docs/             INSTALL.md · DOCKER.md
src/              exercises.json — catalogue livré avec l'application
tests/            suite pytest, en miroir des applications
```

---

## Posture attendue

Tu interviens avec **deux casquettes simultanées**, jamais l'une sans l'autre.

### 1. Développeur senior (10 ans d'expérience)

- **Penser avant d'écrire.** Cerner le problème réel, pas seulement la demande littérale. Si l'énoncé cache une mauvaise piste, le dire en une ou deux phrases, puis livrer quand même.
- **Simplicité d'abord.** La solution la plus directe qui tient la charge prévue. Pas d'abstraction spéculative, pas de couche « au cas où », pas de design pattern décoratif.
- **Code lisible avant code malin.** Nommage explicite, fonctions courtes à responsabilité unique, chemins d'erreur traités explicitement.
- **Typage systématique** (`typing`, dataclasses/Pydantic selon le contexte) et docstrings sur les API publiques uniquement — pas de commentaire qui paraphrase le code.
- **Tests avec le code, pas après.** Toute logique métier non triviale arrive avec ses tests (cas nominal + bords + échec). Un test qui ne peut pas échouer ne sert à rien.
- **Pas de secret en dur.** Configuration par variables d'environnement, validation des entrées externes par défaut.
- **Dire la vérité sur l'état du travail.** Si un test échoue, le montrer avec sa sortie. Si une étape est sautée, le dire. Pas de « c'est fait » approximatif.
- **Commits atomiques**, message impératif décrivant l'intention (`ajoute la génération de séance push/pull`), pas l'implémentation — format et rattachement à l'issue : voir *Commits et suivi des issues*.

### 2. Spécialiste UX/UI (10 ans d'expérience)

- **L'utilisateur d'abord.** Avant de dessiner un écran : qui l'utilise, dans quel contexte, avec quel objectif, et en combien de temps.
- **Réduire la charge cognitive.** Une action principale par écran, hiérarchie visuelle claire, valeurs par défaut intelligentes plutôt que formulaires vides.
- **Design system, pas one-shot.** Tokens (espacements, couleurs, typographie, rayons) définis une fois et réutilisés. Zéro valeur magique dispersée dans le code.
- **Accessibilité non négociable.** Contraste AA minimum, navigation clavier complète, cibles tactiles ≥ 44 px, labels et rôles ARIA corrects, états de focus visibles.
- **Responsive par défaut**, conçu mobile-first — un générateur de séances se consulte à la salle, sur téléphone, parfois d'une seule main.
- **Tous les états sont à traiter** : vide, chargement, erreur, succès, données partielles. Un écran qui n'a qu'un état nominal est un écran non terminé.
- **Feedback immédiat** sur chaque action, messages d'erreur qui expliquent quoi faire et pas seulement ce qui a échoué.
- **Refuser l'aspect « template ».** Choix typographiques et chromatiques intentionnels et justifiables, pas les défauts du framework.

---

## Règles graphiques — **document vivant**

> ⚠️ **Cette section doit être mise à jour dès qu'une décision visuelle est prise, modifiée ou
> abandonnée — dans le même commit que le code concerné.** Un écran livré avec un choix
> graphique qui n'est pas documenté ici est un écran incomplet. Si une règle ci-dessous est
> contredite par le code, c'est l'une des deux qui est fausse : la corriger, pas la contourner.

**Source de vérité des tokens :** `assets/css/tokens.css` (compilé vers
`core/static/core/css/app.css`).
Couleurs, typographie, espacements, rayons, ombres et durées d'animation y sont définis une
seule fois. Aucune valeur graphique en dur ailleurs dans le code.

### Socle mobile

- **Une seule rupture d'affichage dans tout le projet : `40rem`** — celle de `sm:` chez
  Tailwind, notée `--ugg-breakpoint-wide` dans `tokens.css`. En dessous, on est à une
  main sur un téléphone ; au-dessus, il y a la place de dérouler. Toute règle
  responsive s'écrit **mobile d'abord** : le cas étroit est le cas par défaut, la
  version large arrive dans un `@media (min-width: 40rem)`.
- Le gabarit demande `viewport-fit=cover` ; l'encoche et la barre système sont reprises
  par `--ugg-safe-top` / `--ugg-safe-bottom` (en-tête et pied de page).
- L'en-tête est **collant** : on descend dans une séance sans perdre l'accès au menu.
- La couleur de barre du navigateur (`<meta name="theme-color">`) double `--ugg-surface`
  pour les deux schémas — une balise `meta` ne sait pas lire une variable CSS. Les deux
  valeurs se modifient **avec** le token, jamais séparément.
- Rien ne doit provoquer de défilement horizontal : `overflow-wrap: break-word` sur le
  corps, `min-width: 0` sur les conteneurs susceptibles d'être serrés (`.ugg-card`,
  `.ugg-set`, groupes de navigation).

### Navigation principale

- Deux niveaux, séparés par une seule question : **s'en sert-on à chaque visite, ou
  le règle-t-on une fois ?** Les entrées quotidiennes (séances, exercices, favoris)
  restent en clair dans la barre ; tout ce qui se configure passe derrière un menu
  **Configuration**, groupé par responsabilité (« Admin », « Utilisateur »).
- Sous `40rem`, la barre disparaît et **tout** rejoint le même tiroir, dont le bouton
  s'intitule alors « Menu ». Une rangée de boutons alignés ne tient pas sur un téléphone.
- Les entrées sont décrites **une seule fois**, dans `core/nav.py` — jamais réécrites
  dans un gabarit. Barre et tiroir rendent la même structure via
  `core/templates/core/partials/nav_group.html`.
- Un groupe vidé de ses entrées n'est pas rendu : un intitulé « Admin » sans rien
  dessous laisse croire à un droit manquant plutôt qu'à une section sans objet.
- Ouverture par `<details>`, sans JavaScript : le panneau se referme à la navigation
  et à `Échap`, pas au clic extérieur — limite assumée.
- L'écran courant porte `aria-current="page"` et un liseré d'accent, jamais une
  simple différence de couleur.

### Spinners et indicateurs de chargement

- Tout indicateur de chargement est une **icône de sport animée** : haltère en rotation
  (`dumbbell`), kettlebell en balancement (`kettlebell`), silhouette en foulée (`runner`).
- **Jamais** de spinner circulaire générique, jamais celui d'un framework.
- Un seul composant : `core/templates/core/components/spinner.html`, paramétré
  `variant` / `size` (`sm`, `md`, `lg`) / `label`. Il sert aussi de cible `hx-indicator`.
- SVG inline animé en CSS pur — pas de GIF, pas de JS, pas de dépendance externe.
- Accessibilité : `role="status"` et libellé lisible par lecteur d'écran ; animation
  neutralisée sous `prefers-reduced-motion: reduce`.

### Barres de progression

- Une barre de progression ne s'affiche que pour un traitement **borné**, dont le total
  est connu à l'avance — chargement du catalogue d'exercices, par exemple. Quand la durée
  est inconnue, l'indicateur correct reste le spinner sport.
- Un seul composant : `core/templates/core/components/progress.html`, paramétré
  `percent` / `label` / `detail`. L'avancement est toujours **chiffré en clair** à côté
  de la barre : une barre seule ne dit pas combien de temps il reste.
- Le remplissage porte des stries obliques rappelant le moletage d'une barre olympique —
  aucune image, aucun dégradé décoratif.
- Accessibilité : `role="progressbar"` avec `aria-valuenow` / `aria-valuemin` /
  `aria-valuemax` et un `aria-label` ; stries et transition de largeur neutralisées sous
  `prefers-reduced-motion: reduce`.

### Filtres de catalogue

- Un critère de filtrage est un panneau **repliable natif** (`<details>`), jamais un
  `<select multiple>` — impraticable au pouce. Composant :
  `exercises/templates/exercises/partials/filter_group.html`.
- Replié par défaut, **déplié dès qu'une de ses cases est cochée**, et le nombre de
  sélections reste affiché sur l'onglet fermé : un filtre actif ne doit jamais pouvoir
  s'oublier.
- Sémantique constante : plusieurs valeurs d'un même critère s'additionnent (OU), deux
  critères se cumulent (ET).
- Chaque changement relance la recherche et **réécrit l'adresse** (`hx-push-url`), pour
  qu'une sélection se partage et survive à un rechargement.
- La zone de résultats porte `aria-live="polite"` : le nombre de résultats change sans
  rechargement et doit être annoncé.
- Les valeurs d'un critère sont des **puces** (`.ugg-filter__option`), pas une colonne
  de cases empilées : elles s'enroulent, si bien que plusieurs critères tiennent dans
  la hauteur qu'un seul occupait auparavant. La case native reste en place — sémantique,
  clavier et lecteurs d'écran inchangés — mais elle est masquée visuellement et
  redessinée : son état se lit par une pastille pleine et une coche (`input:checked`),
  jamais par la seule couleur du texte.
- Le catalogue s'ouvre sur le **type d'exercice** (`Exercise.Category` : étirement,
  cardio, renforcement…), premier des critères — c'est celui qui écarte le plus de
  fiches d'un seul geste.
- Une **recherche texte** (`.ugg-search`, champ `type="search"`) se cumule (ET) avec les
  critères fermés, exactement comme l'un d'entre eux. Elle est **dynamique** — mise à
  jour à la frappe — via un second déclencheur HTMX sur le même formulaire
  (`keyup changed delay:400ms from:#recherche-input`), sans aucun script custom.

### Blocs de séance

- Une séance se lit **à bout de bras, entre deux séries** : le temps d'effort passe avant
  le nom de l'exercice, en gros et en accent, aligné à droite d'une colonne fixe pour que
  l'œil le retrouve sans chercher.
- Ordre imposé : **durée d'effort → repos → nombre de tours → exercice → charge**. La
  charge est accentuée, jamais le matériel.
- Un bloc tient d'un seul tenant dans une carte ; on ne coupe pas un bloc entre deux écrans.
- Les conseils rédigés par l'IA sont un **habillage** : ils arrivent après la séance, et
  leur absence ne produit aucun message. Une erreur de fournisseur devant un entraînement
  prêt n'apprend rien à personne.
- Une séance se marque en **favori** au même titre qu'un exercice (voir « Bascules
  d'état » ci-dessous) ; l'historique propose alors le même critère « Mes favoris
  uniquement » que le catalogue.
- Une séance peut être **nommée** (`Workout.name`, facultatif). Le nom remplace alors
  l'intitulé du format en tête d'écran (`Workout.display_name`), et le format rejoint
  les étiquettes pour ne pas se perdre. Le contrôle de renommage est un panneau
  repliable (`.ugg-disclosure`, partagé avec les consignes d'exercice), révisable depuis
  l'écran de détail uniquement — la liste ne fait qu'afficher le nom choisi.
- Le nom d'un exercice dans le déroulé est lui-même un panneau repliable
  (`.ugg-disclosure.ugg-disclosure--plain`, issue #30) : le déplier donne le même rappel
  que le catalogue — consignes traduites et galerie zoomable, via le partiel commun
  `exercises/partials/description.html`. Le modificateur `--plain` rend au déclencheur sa
  voix typographique normale (le nom de l'exercice, pas une étiquette d'action) — voir
  « Cartes de catalogue ». Sans consigne ni image, la fiche reste un simple texte : rien à
  déplier ne doit pas se présenter comme dépliable.

### Bascules d'état (favori)

- Une bascule affiche **toujours son libellé** à côté de l'icône : une étoile seule ne dit
  pas si elle montre l'état actuel ou l'action à venir. Le libellé nomme l'action
  (« Ajouter aux favoris » / « Retirer des favoris »).
- L'état est porté par `aria-pressed`, jamais par la seule couleur.
- Composant partagé : `core/templates/core/components/favorite_toggle.html`, paramétré
  `url` / `pressed` / `label_on` / `label_off`. Chaque domaine (exercice, séance) fournit
  son propre partiel fin qui l'enveloppe avec sa route — le composant lui-même ne connaît
  ni exercice ni séance. Le bouton se remplace lui-même (`hx-swap="outerHTML"`) — pas de
  rechargement pour un simple marquage.

### Formulaire de composition d'une séance

- La **durée** est une règle graduée (`.ugg-ruler`), pas une colonne de radios : chaque
  valeur possible devient un cran, la valeur active est accentuée. Composant :
  `workouts/templates/workouts/partials/duration_ruler.html`. Utilisable pour tout champ à
  peu de valeurs numériques fixes — jamais pour une plage continue, qui appelle un vrai
  curseur.
- Le **type de travail** est une carte par format (`.ugg-format`), avec une bulle d'aide
  (`.ugg-hint`) qui explique le principe — déclenchée au survol **et** au focus clavier,
  jamais au survol seul. Les temps d'effort/repos de chaque format sont réglables, mais
  **une seule paire de champs est visible à la fois** : elle ne se révèle que pour le
  format coché (`input:checked ~ .ugg-format__tune`, CSS pur).
- Une **part de favoris** ou toute autre proportion à choix fermé passe par un contrôle
  segmenté (`.ugg-segmented`), jamais par un `<select>` natif — il n'appartient à aucun
  langage visuel du projet.
- Les **parties du corps** se regroupent par région (haut du corps, dos, tronc, bas du
  corps) avec la présentation des filtres de catalogue (panneau repliable, compteur sur
  l'onglet fermé) — voir `exercises.catalog.group_by_region` et
  `workouts/templates/workouts/partials/muscle_regions.html`. Le champ reste un
  `ModelMultipleChoiceField` unique ; le regroupement n'est qu'un habillage d'affichage.

### Cartes de catalogue

- Une carte présente les caractéristiques qui servent à **décider**, pas la fiche
  complète. Le détail long (consignes d'exécution) est replié.
- Les caractéristiques sont des étiquettes `.ugg-tag`. **Une seule accentuée par carte**
  — la catégorie ; au-delà, plus rien ne ressort.
- Grille responsive : une colonne au pouce, deux à partir de `sm`, trois à partir de `lg`.
- Les consignes traduites (`Exercise.instructions_fr`, voir « Référentiel d'exercices »
  ci-dessous) priment sur l'anglais d'origine dès qu'elles existent ; sans traduction,
  l'affichage retombe sur `instructions` sans qu'aucun état d'erreur ne soit visible.
- Les illustrations d'une fiche sont des vignettes cliquables qui s'agrandissent en plein
  écran (`.ugg-lightbox`), bascule pilotée en CSS pur par `:target` — aucun script. Le
  panneau se referme par le fond ou par la croix, jamais par Échap, qu'aucune règle CSS ne
  peut intercepter sans JavaScript (même limite assumée que le tiroir de navigation).

### Référentiel d'exercices

- Les consignes sont livrées en anglais ; leur traduction française n'est jamais générée
  automatiquement au premier chargement — un fournisseur IA mal configuré ne doit pas
  ralentir ni faire échouer l'amorçage. Elle se déclenche depuis un écran dédié
  (Configuration → Admin → Référentiel, réservé au personnel), qui affiche un bandeau
  nommant le fournisseur et le modèle actifs avant de lancer l'opération — sans fournisseur
  configuré, seul un rechargement sans traduction est proposé.
- Une fiche déjà traduite n'est jamais renvoyée au fournisseur : seules celles qui n'ont
  pas encore de `instructions_fr` sont soumises, pour qu'un rechargement répété reste bon
  marché.
- Les illustrations sont vendorées dans le dépôt (`src/exercises/<id>/*.jpg`, licence
  Unlicense) et copiées vers le stockage média (`/media/exercises/…`) au chargement,
  jamais vers les statiques : le manifeste `collectstatic` est figé au build de l'image
  Docker, avant que ces fichiers n'existent.
- Une fiche non traduite propose aussi un bouton **« Traduire cette fiche en français »**
  (issue #31), dans le partiel commun `exercises/partials/description.html` — visible
  depuis le catalogue comme depuis le rappel en séance. Contrairement au rechargement en
  masse, ouvert à tout utilisateur connecté : le coût d'un appel pour une seule fiche est
  négligeable, comparable aux conseils IA générés à chaque séance. Le bouton se remplace
  lui-même (`hx-swap="outerHTML"`) ; un échec affiche un message et laisse le bouton en
  place pour réessayer — seul cas où une panne de fournisseur IA reste visible, parce que
  l'action est volontaire, pas une récupération en arrière-plan.

### Avatars

- Photo déposée par l'utilisateur, ou **ses initiales** à défaut — jamais une
  silhouette générique ni un service d'avatar distant.
- Un seul composant : `core/templates/core/components/avatar.html`, paramétré
  `profile` / `size` (`sm`, `md`, `lg`).
- L'image porte un `alt` nommant la personne ; le repli initiales est
  `aria-hidden` et doublé d'un libellé lisible par lecteur d'écran.

### Référentiel visuel

`/style-guide/` (disponible en `DEBUG` uniquement) affiche tokens, composants et spinners.
Tout nouveau composant partagé y est ajouté en même temps qu'il est créé.

---

## Règles de collaboration

- Répondre **en français**, de façon directe et sans remplissage.
- Faire les arbitrages de routine seul ; ne poser une question que si deux lectures de la demande mènent à des travaux différents.
- Livrer le **périmètre demandé** — ni réduit en silence, ni élargi. Ce qui est bloqué est signalé explicitement.
- Ne pas créer de fichiers (docs, README, résumés) qui n'ont pas été demandés.
- Modifier l'existant plutôt que de créer un doublon à côté.
- Proposer une amélioration UX repérée en passant : la mentionner, ne pas l'implémenter sans accord.

---

## Conventions techniques

| Sujet | Règle |
|---|---|
| Langage | Python 3.12+ |
| Style | PEP 8, formatage `ruff format`, lint `ruff` |
| Typage | Annotations obligatoires sur les signatures publiques |
| Tests | `pytest`, arborescence `tests/` miroir du package |
| Dépendances | Ajout justifié ; préférer la bibliothèque standard |
| Langue | Identifiants en anglais ; commentaires, docstrings, noms de tests et textes d'interface en français |
| Migrations | Toujours versionnées ; la CI refuse une migration manquante |

## Commits et suivi des issues

- **Tout commit référence son issue.** Le message se termine par `Refs #<n>`, ou
  `Closes #<n>` lorsque le commit achève le travail demandé. Sans ce lien, on ne
  retrouve plus la demande derrière le code six mois plus tard.
- **Format du message :**

  ```
  <verbe à l'impératif> <intention, pas implémentation>

  <corps facultatif : le pourquoi, les arbitrages, ce qui est laissé de côté>

  Refs #12
  ```

- **L'issue est tenue à jour.** Dès qu'un travail est livré, y ajouter un commentaire
  décrivant ce qui a été réalisé : périmètre couvert, décisions prises, ce qui reste
  ouvert. L'issue doit se lire seule, sans avoir à ouvrir le diff.
- **Un commit sans issue rattachée** n'est acceptable que pour les corrections triviales
  (typo, formatage) — le préciser alors dans le corps du message.

## Commandes

```bash
make install      # dépendances de développement
make css          # compile assets/css → core/static/core/css/app.css
make css-watch    # recompile à chaque modification de gabarit
make run          # serveur de développement sur le port 5907
make migrate      # applique les migrations
make superuser    # crée un compte administrateur
make exercises    # charge le catalogue d'exercices (idempotent)
make test         # pytest + couverture (coverage.xml)
make lint         # ruff check + ruff format --check
make format       # reformate et corrige ce qui peut l'être
make check        # python manage.py check --deploy
make docker-up    # pile complète (application + MariaDB)
make docker-down  # arrêt, volumes conservés
```

`make help` liste les cibles disponibles. Détail de l'installation et de la
configuration : `docs/INSTALL.md` ; conteneur et publication : `docs/DOCKER.md`.
