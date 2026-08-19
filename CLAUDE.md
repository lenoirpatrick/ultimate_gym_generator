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
| Base | SQLite, fichier persisté sur volume en conteneur (`DJANGO_DB_PATH`) |
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
  le règle-t-on une fois ?** Les entrées quotidiennes (séances, exercices, favoris,
  **compte personnel** — consulté trop souvent pour se cacher derrière un menu, issue
  #38) restent en clair dans la barre ; tout ce qui se configure une fois passe derrière
  un menu **Configuration**, groupé par responsabilité (aujourd'hui, un seul groupe :
  « Admin », réservé au personnel — un groupe « Utilisateur » n'a plus lieu d'être
  depuis que le compte a rejoint la barre).
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
  leur absence ne produit aucun message au premier chargement automatique. Une fois des
  conseils affichés, un bouton **« Rafraîchir les conseils »** (`.ugg-btn--ghost`,
  `workouts.views.workout_coaching_refresh`, issue #29 suite) permet d'en redemander
  d'autres — action volontaire, dont l'échec reste cette fois visible (même principe que
  le bouton de traduction d'un exercice) plutôt que silencieux : un message informe que
  les conseils sont indisponibles, et les précédents restent affichés, jamais effacés par
  un rafraîchissement raté.
- Une séance se marque en **favori** au même titre qu'un exercice (voir « Bascules
  d'état » ci-dessous) ; l'historique propose alors le même critère « Mes favoris
  uniquement » que le catalogue.
- La **carte d'une séance dans l'historique** (`workouts/partials/workout_results.html`,
  issue #35 suite) s'empile sous `40rem` : titre/date, indicateurs et bouton favori
  occupent chacun leur propre ligne pleine largeur — les partager sur une seule ligne
  écrasait le titre. À partir de `sm:`, ils reviennent sur une seule ligne qui s'enroule
  (`flex-wrap`), le bouton favori ne s'étirant jamais en pleine largeur (`self-start` /
  `sm:self-auto`).
- Une séance peut être **nommée** (`Workout.name`, facultatif), soit dès la composition
  (`WorkoutForm.name`, issue #44), soit ensuite depuis l'écran de détail. Le nom remplace
  alors l'intitulé du format en tête d'écran (`Workout.display_name`), et le format
  rejoint les étiquettes pour ne pas se perdre. Sur l'écran de détail, le **titre
  lui-même** est le déclencheur du panneau de renommage
  (`.ugg-disclosure.ugg-disclosure--plain`, même patron que le nom d'exercice dans le
  déroulé, issue #44 suite) : un clic dessus l'ouvre, pas de bouton « Renommer » séparé
  à chercher. Un double-clic exigerait un vrai script (aucune détection en CSS pur) —
  écarté au profit de ce déclencheur en un clic, cohérent avec le reste du projet. La
  liste, elle, ne fait qu'afficher le nom choisi.
- Chaque exercice du déroulé porte un bouton **« Changer l'exercice »**
  (`.ugg-btn--ghost`, toujours labellisé, sans confirmation — action réversible d'un
  clic, issue #44) qui le remplace par un autre compatible avec les muscles de la
  séance et le matériel *actuellement* configuré, pas le sous-ensemble figé à la
  génération (`workouts.generator.refresh_exercise`), en évitant si possible les
  doublons du déroulé. Le repos entre chaque exercice (`WorkoutExercise.rest_seconds`)
  reste affiché dans la colonne de temps mais ne se modifie plus depuis cet écran — seul
  le réglage ci-dessous, unique pour toute la séance, est modifiable (issue #44 suite).
- Le repos **entre les tours** de circuit/HIIT, ou entre les blocs de Tabata/Pyramide
  (`Workout.recovery_seconds`, distinct du repos entre exercices ci-dessus) est réglable
  via une **règle graduée** (`.ugg-ruler`, même composant que la durée de la séance à la
  composition) — six crans de 30 s à 3 min, par pas de 30 s
  (`generator.RECOVERY_RULER_SECONDS`) — plutôt qu'un champ libre, dans l'encart des
  exercices (`workouts/partials/recovery.html`), pas caché derrière un panneau repliable :
  un choix soumet aussitôt (`hx-trigger="change"`). Résolu à la génération depuis
  `generator.FORMAT_PERIODS[format].recovery` (ou le réglage du formulaire) et toujours
  concret ensuite, jamais `None`, contrairement à `work_seconds`/`rest_seconds` qui
  restent une simple trace de la demande — la Pyramide (0 par défaut) tombe hors des
  crans de la règle, qui retombe alors sur `RECOVERY_RULER_DEFAULT` (60 s) à l'affichage
  sans changer la valeur enregistrée tant qu'on n'a pas choisi un cran. Le minuteur en
  tenait compte dans son minutage prévisionnel (`generator.Periods.recovery`) sans jamais
  marquer la pause à l'exécution — désormais un pas dédié (`phase: "recovery"`)
  s'intercale entre deux tours ou deux blocs, jamais après le dernier ; distingué de
  l'effort par son libellé (« Récupération ») comme le repos, sans dépendre de la seule
  couleur, et partage sa tonalité.
- Le nom d'un exercice dans le déroulé est lui-même un panneau repliable
  (`.ugg-disclosure.ugg-disclosure--plain`, issue #30) : le déplier donne le même rappel
  que le catalogue — consignes traduites et galerie zoomable, via le partiel commun
  `exercises/partials/description.html`. Le modificateur `--plain` rend au déclencheur sa
  voix typographique normale (le nom de l'exercice, pas une étiquette d'action) — voir
  « Cartes de catalogue ». Sans consigne ni image, la fiche reste un simple texte : rien à
  déplier ne doit pas se présenter comme dépliable.

### Minuteur de séance (issue #35)

- Un bouton **« Lancer la séance »** (`.ugg-btn--primary`) ouvre un `<dialog>` natif
  (`.ugg-timer`, `workouts/partials/timer_modal.html`) : piège de focus, fermeture à
  Échap et retour de focus au déclencheur viennent gratuitement de l'élément, sans
  JavaScript à écrire pour ça — seule règle du projet où un vrai script est nécessaire
  (`core/static/core/js/workout_timer.js`), un décompte ne pouvant pas exister en CSS
  pur. Absent si la séance n'a aucun exercice (`timeline` vide).
- La modale occupe **toute la taille de l'écran**, sur tous les formats — pas de carte
  centrée au-delà de `40rem` comme les autres panneaux du projet : une séance en cours ne
  se consulte pas dans une fenêtre, elle prend l'écran. Contrairement au tiroir de
  navigation et au `.ugg-lightbox`, le clic sur le fond **ne referme pas** la modale — un
  effort en cours ne doit pas s'interrompre d'un geste accidentel ; seuls le bouton
  « Arrêter » et Échap (natif au `<dialog>`) y mettent fin.
- L'ordre chronologique réel — un tour de circuit ou HIIT enchaîne tous ses exercices
  avant de le répéter (round-robin), un Tabata ou une pyramide épuisent un exercice avant
  de passer au suivant — est calculé côté serveur par `workouts.timer.build_timeline`,
  jamais recalculé en JavaScript : le script ne fait qu'égrainer la liste de pas
  (`json_script`) et mettre à jour l'affichage.
- La modale affiche la **timeline simplifiée** (`workouts/partials/timer_timeline.html`,
  un item par exercice avec sa photo — pas un pas par pas du minuteur) et met en
  surbrillance l'exercice en cours (liseré d'accent, jamais la seule couleur). Le pas
  courant porte le temps décompté en grand ; un effort en répétitions (pyramide) affiche
  la cible et attend une confirmation manuelle plutôt qu'un décompte qui n'aurait pas de
  sens.
- Le **tiers bas de l'écran** (`.ugg-timer__current`) reprend l'exercice en cours en
  grand — photo, matériel, muscles principaux — pour s'y référer d'un coup d'œil sans
  chercher la bonne ligne dans la timeline, qui reste au-dessus pour le contexte des pas
  à venir. Alimenté par JavaScript à chaque changement de pas (`highlight()`, dans
  `workout_timer.js`) : il relit la ligne correspondante de la timeline plutôt que de
  dupliquer photo/matériel/muscles dans le JSON du minuteur — une seule source pour ces
  informations. Absent d'exercice sans photo : l'image se masque plutôt que d'afficher
  un cadre vide. Un exercice qui en compte plusieurs les fait défiler toutes les 5 s
  (`startPhotoRotation()`, issue #35 suite) tant que la séance n'est pas en pause — la
  liste complète voyage dans `data-photos` sur la ligne de la timeline (`workouts/
  partials/timer_timeline.html`), séparée par `|`, sur le même principe que
  `data-equipment`/`data-muscles` ; la vignette de la timeline, elle, reste fixe sur la
  première photo.
- Cinq secondes de **préparation**, décomptées avant le premier pas, pour le temps de se
  mettre en place — pas encore comptées dans l'avancement de la séance.
- La **barre de progression** chiffre l'avancement de la séance entière (pas de la seule
  phase en cours) : elle avance en continu au fil du décompte du pas courant, pas par
  à-coups à chaque changement de pas ; la préparation ne compte pas encore. Un effort en
  répétitions y avance dès qu'il est atteint, faute de chronomètre pour le fractionner.
- Trois commandes seulement : **Pause** (indisponible sur un pas en répétitions, rien à
  mettre en pause), **Passer** (avance manuellement, y compris pour confirmer un pas en
  répétitions) et **Arrêter** (`.ugg-btn--danger`, nouvelle variante de `.ugg-btn`).
- Des sons marquent le début de la séance, la fin, chaque changement de phase (début
  d'effort, début de repos), et un bip discret par seconde sur les **quatre dernières
  secondes** de tout décompte (préparation comprise) — **synthétisés via l'API Web
  Audio**, pas des fichiers embarqués : aucune dépendance externe, aucune question de
  licence, fonctionne hors connexion. Uniquement des ondes sinusoïdales ou triangulaires,
  jamais carrées — le buzzer numérique ne correspond à aucune identité sonore du projet.
  Le repos se distingue de l'effort par le libellé affiché autant que par la tonalité,
  jamais par la seule couleur ; la récupération entre tours/blocs (issue #44 suite)
  reprend la tonalité du repos — les deux sont une pause, pas un effort — mais garde son
  propre libellé (« Récupération »).
- Chaque phase du minuteur porte, en plus de son libellé, une couleur constante sur tout
  l'écran (issue #35 suite) : **préparation** en `--ugg-danger` (on démarre, l'urgence du
  compte à rebours), **effort** dans l'accent de marque (`--ugg-accent`, déjà la couleur
  par défaut de `.ugg-timer__phase`), **repos** entre exercices en `--ugg-success`, et
  **récupération** entre tours/blocs en `--ugg-info` — seul usage d'une couleur froide
  dans tout le projet, réservé à cette pause pour ne jamais se confondre avec le repos
  entre exercices. La couleur ne fait que renforcer le libellé, jamais le remplacer.

### Bascules d'état (favori)

- Une bascule affiche **toujours son libellé** à côté de l'icône : une étoile seule ne dit
  pas ce qu'est le bouton. Le libellé est constant, « Favoris » (issue #35 suite) — pas
  une description de l'action (« Ajouter aux favoris » / « Retirer des favoris », trop
  long pour rester compact partout, y compris sur la carte d'historique d'une séance) ;
  l'état, lui, se lit au remplissage de l'étoile (pleine si favori, contour sinon) et à
  `aria-pressed`, jamais au texte ni à la seule couleur.
- Composant partagé : `core/templates/core/components/favorite_toggle.html`, paramétré
  `url` / `pressed` uniquement — le libellé est fixe dans le composant, pas transmis par
  l'appelant. Chaque domaine (exercice, séance) fournit son propre partiel fin qui
  l'enveloppe avec sa route — le composant lui-même ne connaît ni exercice ni séance. Le
  bouton se remplace lui-même (`hx-swap="outerHTML"`) — pas de rechargement pour un
  simple marquage. Compact (cible tactile 44 px de haut conservée, mais resserré en
  largeur) pour tenir à côté d'un titre sans le pousser hors de sa ligne.

### Formulaire de composition d'une séance

- Le **nom** (`WorkoutForm.name`, facultatif, issue #44) est le premier champ du
  formulaire — se nommer avant de composer plutôt qu'après. Repris tel quel par
  `Workout.name` à la génération ; reste modifiable ensuite depuis l'écran de détail
  (voir « Blocs de séance »).
- La **durée** est une règle graduée (`.ugg-ruler`), pas une colonne de radios : chaque
  valeur possible devient un cran, la valeur active est accentuée. Composant :
  `workouts/templates/workouts/partials/duration_ruler.html`. Utilisable pour tout champ à
  peu de valeurs numériques fixes — jamais pour une plage continue, qui appelle un vrai
  curseur. Onze crans de 5 en 5 minutes, de 10 à 60, 30 par défaut (issue #32) ; l'unité ne
  se répète pas sur chaque cran (illisible sur un téléphone) mais se porte une fois par le
  libellé du champ, « Durée (minutes) ».
- Le **type de travail** est une carte par format (`.ugg-format`), avec une bulle d'aide
  (`.ugg-hint`) qui explique le principe — déclenchée au survol **et** au focus clavier,
  jamais au survol seul. Les intervalles de chaque format sont réglables (effort/repos/
  récupération entre tours — cette dernière toujours présente, y compris pour la
  pyramide, issue #44 suite ; pour la pyramide, le pic de répétitions à la place de
  l'effort, issue #34) : le panneau
  « Ajuster les réglages » de **chaque** carte se déplie indépendamment de son radio —
  masquer celui d'un format tant qu'il n'était pas coché avait rendu le réglage
  introuvable en pratique (issue #36 suite : rien ne montrait qu'il fallait d'abord
  sélectionner le format pour seulement pouvoir l'ouvrir). Consulter ou régler la carte
  d'un format non retenu ne change rien à la génération ; seules la couleur de bordure et
  du libellé (`.ugg-format:has(input:checked)`) indiquent celui réellement choisi. Le
  radio n'est associé qu'à la tête de carte (`.ugg-format__select`, un `<label>` distinct)
  — jamais à la carte entière : un `<summary>` imbriqué dans le `<label>` du radio partage
  son clic avec lui, et le panneau « Ajuster les réglages » n'ouvrait plus (issue #32). Le
  panneau reste un déclencheur `<details>` indépendant, hors de tout `<label>`. Le pic de
  la pyramide est un plancher fixe (`generator.PYRAMID_FLOOR_REPS`, 6) et un pic réglable — jamais une
  suite de répétitions éditable pas à pas, qui suggérerait une précision que l'algorithme
  de remplissage ne garantit pas ; le nombre d'exercices retenus s'adapte automatiquement
  au pic choisi, une pyramide étant un bloc indivisible (`generator._pyramid_shapes`).
- Une **part de favoris** ou toute autre proportion à choix fermé passe par un contrôle
  segmenté (`.ugg-segmented`), jamais par un `<select>` natif — il n'appartient à aucun
  langage visuel du projet.
- Les **parties du corps** se regroupent par région (haut du corps, dos, tronc, bas du
  corps) avec la présentation des filtres de catalogue (panneau repliable, compteur sur
  l'onglet fermé) — voir `exercises.catalog.group_by_region` et
  `workouts/templates/workouts/partials/muscle_regions.html`. Le champ reste un
  `ModelMultipleChoiceField` unique ; le regroupement n'est qu'un habillage d'affichage.
- Le **matériel pris en compte** se coche directement dans son encart, en puces
  `.ugg-filter__option--standalone` — jamais en lecture seule (issue #32). Un choix par
  matériel réellement configuré, coché par défaut, mais indépendant de la configuration
  elle-même (`accounts:equipment`) : décocher ici n'écarte ce matériel que pour cette
  séance. Le poids du corps reste une étiquette fixe, non togglable — il ne se déclare
  pas. Champ construit dynamiquement dans `WorkoutForm.__init__` (nécessite `user`),
  transmis à `workouts.generator.generate` qui l'intersecte avec le matériel réellement
  possédé — la liste soumise ne peut jamais accorder un matériel non configuré.

### Matériel de l'utilisateur (`accounts:equipment`, issue #37)

- Le **mode de charge** (sans charge / figée / réglable) se choisit par puces
  `.ugg-segmented` (`EquipmentForm.Meta.widgets = {"mode": forms.RadioSelect}`), jamais
  par `<select>` — un `<select>` n'aurait permis aucune bascule CSS des champs qui en
  dépendent. Seul le groupe du mode coché se révèle (`.ugg-equipment__weights` en mode
  figé, `.ugg-equipment__range` en mode réglable), sur le même patron `:has()` que
  `.ugg-format__tune` : les montrer tous deux en permanence avait fini par rendre
  introuvable celui qu'on cherchait. Chaque ligne du formset porte sa propre classe de
  portée, `.ugg-equipment-row` — les sélecteurs `:has()` ciblent
  `input[name$="-mode"][value="…"]`, qui fonctionne quel que soit l'index du formset
  Django, sans jamais retomber dans le piège d'un sélecteur trop large qui masquerait
  aussi d'autres champs (voir issue #36 suite, `.ugg-format input`).
- Une **icône** (`core/components/equipment_icon.html`) suit le matériel choisi,
  superposée à l'intérieur du `<select>` de chaque ligne — pas affichée en dessous
  (issue #43) : `.ugg-equipment__select` porte le positionnement relatif, le `<select>`
  reçoit la marge qui lui laisse la place à gauche. Un pictogramme par valeur
  déclarable (`accounts.forms.DECLARABLE_EQUIPMENT_CHOICES`) est rendu, un seul visible
  via `.ugg-equipment-row:has(select[…] option[value="…"]:checked)`. Purement décoratif
  (`aria-hidden`) — le nom du matériel reste toujours affiché en texte à côté ; si
  `:has()` sur un `<option>:checked` n'est pas pris en charge par un navigateur,
  l'icône reste simplement invisible, sans rien retirer au formulaire.
- Le **poids du corps** (`Exercise.Equipment.BODY_ONLY`) ne fait pas partie du matériel
  déclarable : `workouts.generator.eligible_exercises` le rend systématiquement
  disponible, quelle que soit la configuration de l'utilisateur — le proposer ici
  laisserait croire qu'il faut le cocher comme le reste. Exclu à la fois du `<select>`
  (`EquipmentForm.__init__`) et des icônes (même constante partagée).
- Les lignes s'affichent **dans l'ordre où elles ont été déclarées**, pas alphabétique
  (`UserEquipment.Meta.ordering = ("id",)`) : c'est dans cet ordre qu'elles existent
  pour l'utilisateur qui les a saisies.
- Une ligne déjà enregistrée se **retire dynamiquement** (issue #41) : un bouton
  `.ugg-btn--danger` (`hx-post` vers `accounts:equipment_delete`, confirmation via
  `hx-confirm`) supprime la ligne aussitôt, sans case à cocher ni réenregistrement de
  tout le formulaire. La réponse reswape le bloc entier des lignes
  (`accounts/partials/equipment_rows.html`, `#materiel-lignes`) plutôt que la seule
  ligne visée : `TOTAL_FORMS` et la numérotation des lignes restantes doivent rester
  cohérents, y compris quand la ligne retirée n'était pas la dernière.

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

### Favicon

- `core/static/core/favicon.svg` — un haltère (mêmes tracés que le spinner
  `dumbbell`, voir « Spinners et indicateurs de chargement ») en accent
  citron (`--ugg-lime-500`) sur fond graphite (`--ugg-graphite-950`), pas
  l'icône par défaut du framework. Fond volontairement fixe, indépendant du
  thème clair/sombre de la page : un onglet de navigateur ne suit pas
  `prefers-color-scheme` de la même façon qu'une page, une seule version
  suffit.
- Un seul fichier SVG (`<link rel="icon" type="image/svg+xml">`,
  `core/templates/core/base.html`), sans PNG/ICO généré ni build supplémentaire
  — cohérent avec le zéro dépendance déjà en place pour les spinners.

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

- **Tout commit référence son issue, deux fois.** L'identifiant apparaît dans le
  **titre** (`(#12)` en fin de première ligne) autant que dans le **corps**
  (`Refs #12` / `Closes #12`) : le titre seul fait le lien direct dans un
  `git log --oneline` ou la liste des commits GitHub, sans avoir à ouvrir le
  message complet ; le corps porte le mot-clé (`Closes`/`Fixes`) que GitHub
  reconnaît pour fermer l'issue automatiquement à la fusion. Sans ce lien, on
  ne retrouve plus la demande derrière le code six mois plus tard.
- **Format du message :**

  ```
  <verbe à l'impératif> <intention, pas implémentation> (#12)

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
make docker-up    # pile complète (application, base SQLite persistée)
make docker-down  # arrêt, volumes conservés
```

`make help` liste les cibles disponibles. Détail de l'installation et de la
configuration : `docs/INSTALL.md` ; conteneur et publication : `docs/DOCKER.md`.
