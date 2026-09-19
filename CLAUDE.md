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
| Base | SQLite, fichier persisté (`DJANGO_DB_PATH`) |
| Configuration | `django-environ`, tout par variables d'environnement |
| Interface | Gabarits Django + HTMX 2 (vendoré) + Tailwind CSS 4 (CLI autonome, zéro Node) |
| Chiffrement | Fernet (`cryptography`) pour les clés d'API en base |
| Fournisseurs IA | Anthropic (SDK officiel), Gemini / Mistral / Ollama (REST via httpx) |
| Comptes | Mono-utilisateur par défaut, multi-utilisateurs pris en charge ; SSO OpenID Connect facultatif (`mozilla-django-oidc`) |
| Serveur | Gunicorn + WhiteNoise |
| Qualité | `ruff`, `pytest` + `pytest-django` + couverture, SonarCloud |

```
assets/css/       tokens.css (SOURCE DE VÉRITÉ graphique), components.css, input.css
config/settings/  base (seul jeu de réglages) · test
accounts/         utilisateur (avatar, mesures), authentification, SSO, gestion des comptes
aiproviders/      credentials chiffrés, registre des fournisseurs, adaptateurs, /settings/ai/
exercises/        catalogue d'exercices, import par lots, écran de chargement
health/           données Apple HealthKit (poids, activités), import, API, page d'analyse
core/             gabarit de base, composants, spinners, /healthz, /style-guide/
docs/             INSTALL.md
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

### Navigation principale (issue #76)

- Trois groupes, par **domaine** plutôt que par fréquence d'usage : **UGG**
  (l'entraînement — séances, exercices, favoris), **Apple Santé** (données
  importées d'Apple Health — analyse, import ; identifiée par une icône
  cœur-pulsation dédiée, jamais le logo Apple lui-même : une marque déposée ne
  se reproduit pas) et **Compte** (identité, réglages, déconnexion). Remplace
  l'ancien partage à deux niveaux « quotidien vs configuré une fois » : avec
  trois domaines de poids comparable, grouper par sujet se lit mieux que
  grouper par fréquence.
- **Configuration** (IA, Référentiel, Comptes — réservé au personnel) est un
  **sous-groupe de Compte**, pas un niveau de menu séparé : une section
  repérée par son propre intitulé à l'intérieur du panneau Compte, jamais un
  second `<details>` imbriqué dans le premier — inutile de complexifier
  l'ouverture pour un menu qui n'a jamais plus de trois niveaux.
- **Barre (≥ 40rem)** : un **menu déroulant par groupe** — trois boutons
  `<details>` indépendants (UGG ▾ / Apple Santé ▾ / Compte ▾), chacun ouvrant
  son propre panneau. **Sous `40rem`**, les trois disparaissent au profit d'un
  tiroir unique (bouton « Menu »), qui liste les trois groupes l'un sous
  l'autre — une largeur de téléphone ne tient pas trois boutons de menu côte
  à côte.
- Les entrées sont décrites **une seule fois**, dans `core/nav.py`
  (`NavGroup`/`NavLink`, dataclasses immuables) — jamais réécrites dans un
  gabarit. Barre et tiroir rendent la même structure :
  `core/templates/core/partials/nav_dropdown.html` (l'enveloppe `<details>`
  de la barre) inclut `nav_group.html` (contenu : intitulé, liens,
  sous-groupe, liens de fin), lui-même repris tel quel dans le tiroir. La
  déconnexion (`NavLink.is_logout`) est la seule entrée qui n'est pas une
  navigation GET — `nav_link.html` la rend comme un formulaire POST plutôt
  qu'un lien.
- Un groupe — ou un sous-groupe — vidé de ses entrées n'est pas rendu :
  `core.nav.menu_for(user)` filtre récursivement selon `is_staff` et retire
  toute section devenue vide (`NavGroup.is_empty`) ; un intitulé
  « Configuration » sans rien dessous laisserait croire à un droit manquant
  plutôt qu'à une section sans objet pour ce compte.
- Ouverture par `<details>`, sans JavaScript : le panneau se referme à la
  navigation et à `Échap`, pas au clic extérieur — limite assumée.
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
  `<select multiple>` — impraticable au pouce. Composant partagé :
  `core/templates/core/components/filter_group.html` (extrait d'`exercises` vers
  `core` quand `health` en a eu besoin à son tour, issue #73 — les dataclasses
  `Option`/`FilterGroup` et `selected_values()` vivent maintenant dans
  `core/filtering.py`, réutilisées par `exercises.filters` et `health.filters`).
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

### Import Apple Health (issues #70, #74, #75, #78, #79)

- Contrairement au catalogue d'exercices — un petit JSON versionné, ré-échantillonnable
  par tranches — un export Apple Health est un **unique fichier XML** à parcourir
  séquentiellement, potentiellement volumineux : le re-parcourir par tranches à chaque
  appel HTMX coûterait un balayage complet à chaque tranche (O(n²)). L'import se fait
  donc en **une seule requête synchrone** (`health.importer.parse_export`), bornée par
  `APPLE_HEALTH_IMPORT_MAX_BYTES` (4 Go par défaut — plusieurs années d'historique
  HealthKit dépassent vite 2 Go, et continuent de croître à chaque nouvel export ;
  à relever encore via l'environnement si le fichier déposé dépasse quand même ce
  plafond, aucune autre limite côté application, issue #74).
- Le formulaire d'import propose un champ **« Importer depuis » facultatif**
  (`HealthImportForm.since`) : les enregistrements antérieurs sont ignorés
  (comptés dans `ImportResult.skipped_before_since`, affiché dans le résumé). Un
  seul champ date couvre à la fois « depuis une date précise » et « depuis une
  année » (1ᵉʳ janvier de l'année visée) plutôt que deux champs redondants — la
  taille du fichier déposé ne change pas, seul ce qui en est retenu diminue.
- La durée totale n'étant pas connue à l'avance, l'indicateur correct reste le **spinner
  sport** (`hx-indicator`, patron des conseils IA de séance), jamais une barre de
  progression — cohérente avec la règle des « Barres de progression » ci-dessus.
- Le fichier est lu avec `defusedxml` plutôt que `xml.etree` directement : un fichier
  déposé par l'utilisateur reste une entrée non fiable, à l'abri des attaques XML
  classiques (entités externes, expansion d'entités).
- Idempotent par construction : `WeightMeasurement`/`Activity` portent une contrainte
  d'unicité sur leur clé naturelle (utilisateur + instant de mesure, ou utilisateur +
  type + début d'activité — un export Apple Health classique ne porte aucun identifiant
  stable par enregistrement). Un réimport met donc à jour plutôt que dupliquer. La même
  fonction d'upsert (`health.ingest`) sert l'import fichier et l'API d'ingestion
  (issue #71), pour que les deux ne divergent jamais sur cette clé.
- Un type d'activité HealthKit non couvert par `health.importer.WORKOUT_TYPE_MAP`
  est importé quand même, classé `Activity.ActivityType.OTHER` — traiter la donnée
  comme un coach professionnel ne consiste pas à en jeter une partie silencieusement.
- Les pas (`HKQuantityTypeIdentifierStepCount`, issue #75) sont exportés en une
  multitude de petits intervalles, jamais un total par jour : `parse_export` les
  **agrège en mémoire pendant le parcours** (`steps_by_date`), puis écrit un seul
  total par jour à la fin (`health.ingest.upsert_daily_steps`). La clé naturelle
  de `DailySteps` est donc la date, pas l'instant — un réimport **remplace** le
  total du jour plutôt que de l'additionner une seconde fois.
- Les pas ne se somment **jamais directement par jour** (issue #78) : iPhone et
  Apple Watch enregistrent souvent les mêmes pas en double sur des intervalles
  qui se recouvrent, quand les deux sont portés/à proximité. `parse_export`
  agrège d'abord par **(source, jour)**, et retient pour chaque jour le
  **maximum atteint par une seule source** — l'hypothèse la plus proche de ce
  que fait l'app Santé elle-même, plutôt que la somme de mesures redondantes.
- La durée d'une activité (`Activity.duration_seconds`) est un **champ stocké**,
  pas calculé depuis `ended_at - started_at` (issue #79) : cet écart horaire
  inclut les pauses (feu rouge, calibrage GPS…) et peut représenter près du
  double du temps d'effort réel qu'affiche l'app Santé. `health.importer` lit
  l'attribut `duration`/`durationUnit` de chaque `<Workout>` quand il existe ;
  à défaut (export sans l'attribut, activité créée via l'API #71 sans
  `duration_seconds` explicite), `Activity.save()` se replie lui-même sur
  l'écart horaire — repli centralisé au niveau du modèle, jamais dupliqué chez
  chaque appelant. Allure et volume d'activité (page d'analyse) s'appuient
  tous les deux sur ce champ, jamais sur l'écart horaire brut.

### API d'ingestion à distance (issue #71)

- `POST /sante/api/ingestion/` accepte les mêmes données que l'import fichier (poids,
  activités), pour un raccourci iPhone ou une application tierce qui envoie directement
  ses mesures. Authentifié par **clé API par utilisateur** (`health.ApiKey`), **hachée
  à sens unique** (`make_password`, comme un mot de passe) plutôt que chiffrée — à la
  différence des credentials IA d'`aiproviders`, cette clé n'a jamais besoin d'être
  relue en clair, seulement vérifiée. Elle n'est donc affichée **qu'une fois**, à sa
  création (`/sante/cles-api/`), pas de nouvelle entrée dans la navigation globale — un
  réglage secondaire, au même titre que le matériel de l'utilisateur, atteint depuis la
  page d'analyse plutôt que depuis la barre.
- Hors session par nature (`@csrf_exempt`, pas de `@login_required` : l'authentification
  est manuelle via `health.auth.authenticate_request`) et exempté de
  `FirstRunMiddleware` (`accounts/middleware.py`) — un point d'entrée machine-à-machine
  ne doit jamais être redirigé vers l'écran d'amorçage.
- Une entrée invalide dans un lot n'empêche pas les autres d'être appliquées : la
  réponse détaille les erreurs par entrée plutôt que de rejeter l'envoi entier.

### Page d'analyse (issues #72, #75, #80, #81, #83, #84)

- KPI et graphiques sur **Chart.js vendoré** (`core/static/core/js/chart.min.js`, même
  principe que HTMX : un seul fichier minifié déposé tel quel, aucun bundler). Chargé
  uniquement sur cette page (`{% block extra_scripts %}` de `core/base.html`), pas
  globalement.
- Les données voyagent en JSON via `json_script` (`health/partials/dashboard_results.html`,
  même technique que la timeline du minuteur de séance) plutôt que par un appel réseau
  séparé. Le bloc de résultats étant remplacé par HTMX à chaque changement de filtre
  (#73), `core/static/core/js/health_charts.js` réinitialise les graphiques sur
  `htmx:afterSettle`, en détruisant les instances précédentes avant d'en recréer.
- Couleurs des séries : uniquement les tokens existants (`--ugg-accent` pour les quatre
  séries — poids, volume, allure, pas). `--ugg-info`, seule couleur froide du projet,
  reste réservé à la récupération du minuteur (voir plus haut) ; il n'a pas été
  réutilisé ici pour ne pas rouvrir cette règle.
- KPI « Pas moyens (jour) » : moyenne sur les jours **effectivement importés** dans la
  période, jamais complétée à zéro pour les jours sans total — une moyenne qui inclut
  des zéros artificiels sous-évalue l'activité réelle plutôt que de simplement ignorer
  les jours sans donnée.
- Indicateur clé (KPI) : composant partagé `core/templates/core/components/stat_tile.html`
  (label, valeur en gros, tendance). La tendance se lit à la couleur (`--ugg-success`/
  `--ugg-danger`) **et** à un signe explicite (▲/▼ + delta chiffré) — jamais la seule
  couleur, et le sens « bon/mauvais » n'est pas universel (perdre du poids peut être
  l'objectif ou non) : la convention prise ici est `--ugg-danger` pour une hausse de
  poids, propre à cette page.
- Filtres : période (choix fermé 7j/30j/90j/tout) en **contrôle segmenté**
  (`.ugg-segmented`, règle déjà en vigueur pour tout choix fermé) — jamais un
  `<details>`, réservé aux critères à choix multiples comme le type d'activité (panneau
  repliable partagé avec le catalogue, voir « Filtres de catalogue »). KPI, graphiques
  et liste d'activités affichée partagent le même filtrage (`health.filters`) : jamais
  deux logiques de restriction séparées qui pourraient diverger.
- Entrée de navigation « Analyse » dans le groupe **Apple Santé**
  (`core/nav.py`, voir « Navigation principale ») — consultée régulièrement,
  pas un réglage ponctuel derrière Configuration.
- Les calories (`Activity.active_energy_kcal`, capturées dès #70) apparaissent
  sur chaque carte d'activité (`.ugg-tag`, issue #83) et en KPI agrégé
  « Calories actives » sur la période.
- Un graphique **sans série** sur la période/le filtre courant ne s'affiche
  pas (issue #84) — calculé côté serveur (`health.analytics.ChartData.has_*`),
  jamais laissé en carte vide : `health.views.dashboard` passe l'objet
  `ChartData` au gabarit pour ces conditions, distinct du dict JSON
  (`.as_dict()`) lu par `health_charts.js` — deux formes du même calcul.
- Tous les états traités : aucune donnée importée (`empty_state.html`, lien vers
  l'import), période/types filtrés sans résultat, chargement (spinner `hx-indicator`).
- Chaque graphique dont une carte s'affiche propose un bouton **« Agrandir »**
  (`.ugg-btn--ghost`, issue #80) qui ouvre le même graphique en grand dans une
  `.ugg-lightbox` (`:target`, CSS pur — même bascule que les photos d'exercice) :
  seul le contenu diffère, un panneau (`.ugg-lightbox__panel`) plutôt qu'une
  image, dimensionné en unités fluides (`min(92vw, 64rem)` / `min(80vh, 34rem)`)
  pour tenir sur mobile comme en grand écran sans règle responsive dédiée.
  L'aperçu (petite carte) reste une image statique ; l'agrandissement instancie
  une **seconde** instance Chart.js distincte (canvas `chart-{clé}-large`),
  créée à l'ouverture seulement — un canvas cache derrière `display:none` a une
  taille nulle, Chart.js ne peut pas y dessiner avant que `:target` ne l'affiche
  (`core/static/core/js/health_charts.js`, sur l'évènement `hashchange` que
  produit le clic sur l'ancre, **et** un appel explicite au chargement de la
  page — un lien partagé ou un rechargement pendant qu'un graphique est déjà
  ouvert n'émet aucun `hashchange`, l'omettre laissait le panneau vide).
- Navigation dans le graphique agrandi via **chartjs-plugin-zoom** vendoré
  (`core/static/core/js/chartjs-plugin-zoom.min.js`, même principe que
  `chart.min.js` : un seul fichier déposé tel quel, aucun bundler) : molette
  et pincement zooment sur l'axe des temps (`mode: "x"`), glisser déplace la
  plage visible. Fonctionne sans Hammer.js (dépendance facultative du plugin,
  non vendorée : seul le pincement tactile s'en passerait, dégradation
  silencieuse). Un bouton **« Réinitialiser le zoom »** (`chart.resetZoom()`)
  ramène à la plage d'origine. Jamais activé sur l'aperçu — seule
  l'instance de la lightbox reçoit les options `plugins.zoom`.

### Suppression, édition et recherche d'activités (issue #81)

- Une activité importée peut être **supprimée** (`.ugg-btn--danger`, `hx-confirm`)
  ou voir son **type corrigé** (`<select>` dans son propre `.ugg-field__control`,
  `hx-trigger="change"`) directement depuis sa carte — jamais un simple marquage,
  la donnée source (export Apple Health, ou l'API #71) restant elle-même incorrecte.
  Les deux actions (`health.views.activity_delete`/`activity_edit_type`) réutilisent
  `hx-include="#filtre-analyse"` (id posé sur le `<form>` de filtre) pour faire
  voyager période/types/recherche courants dans leur propre requête, et rendent le
  même fragment `dashboard_results.html` que le filtrage : la vue reste celle sur
  laquelle l'utilisateur travaillait, jamais réinitialisée à l'action.
- Comme les modèles Apple Health n'ont pas d'identifiant stable, l'idempotence de
  l'import repose sur une **clé naturelle** (`user + instant` pour un poids,
  `user + type + début` pour une activité, `health.ingest`). Sans mécanisme
  dédié, une entrée supprimée — ou dont le type est corrigé — reviendrait donc
  telle quelle au prochain réimport ou au prochain appel de l'API #71. Un modèle
  `ExcludedImport` (`user`, `kind`, `natural_key`) enregistre ces clés, consultées
  par `health.exclusions` **avant** chaque écriture dans `health.ingest.upsert_weight`/
  `upsert_activity` — un seul point de passage, commun au fichier et à l'API. La
  clé se normalise toujours en UTC (`exclusions._instant`, `.astimezone(UTC)`) :
  un export porte l'heure locale au moment de la mesure, la base la relit toujours
  normalisée — sans cette conversion, la même seconde produirait deux clés
  différentes selon la provenance et l'exclusion ne matcherait jamais.
- `upsert_weight`/`upsert_activity` renvoient désormais un **tri-état** :
  `True` (créé) / `False` (mis à jour) / `None` (exclu, rien écrit) — tout appelant
  doit distinguer les trois, jamais traiter le retour comme un simple booléen.
  `ImportResult` (import fichier) et la réponse JSON de l'API #71 comptent les
  exclusions séparément (`weights_excluded`/`activities_excluded`), affichées à
  l'utilisateur (`import_panel.html`) pour qu'un réimport n'ait pas l'air d'avoir
  « perdu » des lignes sans explication.
- Corriger le type **déplace** l'activité vers une nouvelle clé naturelle (le type
  en fait partie) : `activity_edit_type` exclut l'**ancienne** clé (calculée avant
  la modification) avant de sauvegarder le nouveau type — sans quoi un réimport
  recréerait la version fautive à côté de la version corrigée.
- La **recherche texte** (`.ugg-search`, champ `q`, même patron dynamique que le
  catalogue d'exercices — `hx-trigger="change, keyup changed delay:400ms from:#…"`)
  se cumule (ET) avec période et types : elle porte sur la source de l'activité
  (`source__icontains`) et sur le libellé traduit du type (résolu côté Python,
  le type étant stocké sous son code HealthKit, pas son libellé affiché).

### Rappel d'exercice associé à une activité (issue #82)

- Un type d'activité HealthKit n'est rapproché d'une fiche du catalogue
  (`health.exercise_link.annotate_linked_exercises`) que lorsque la
  correspondance est **univoque** : course, marche, vélo, aviron, vélo
  elliptique. `strength_training`/`other` recouvrent chacun des dizaines
  d'exercices possibles — aucun choix unique n'y serait fiable — et
  `swimming`/`hiking`/`yoga` n'ont simplement aucun équivalent dans le
  catalogue livré (free-exercise-db) : dans ces cas, rien ne s'affiche
  plutôt qu'un rapprochement hasardeux.
- Le titre de la carte (le type d'activité, ex. « Vélo ») reste lui-même le
  déclencheur du rappel replié — même patron que le nom d'exercice dans le
  déroulé de séance (`.ugg-disclosure.ugg-disclosure--plain`, issue #30) —
  et le partiel commun `exercises/partials/description.html` (consignes,
  galerie) est réutilisé tel quel, jamais dupliqué. Le nom de la fiche
  rapprochée est affiché en toutes lettres au-dessus (« Fiche rapprochée :
  Bicycling ») : le rapprochement n'est pas toujours évident au seul
  intitulé du type.
- `description.html` accepte désormais un `dom_id` facultatif (replié sur
  `exercise.pk` pour ses appelants existants, catalogue et déroulé de
  séance, comportement inchangé) : plusieurs activités du même type
  partagent la même fiche, donc plusieurs rappels de la même fiche peuvent
  apparaître sur une seule page d'analyse. Sans id distinct par activité
  (ici `activity.pk`), les deux rappels dupliqueraient le même id — la
  vignette photo de l'un aurait alors agrandi les deux lightbox à la fois
  (`:target` matche tout élément portant l'id ciblé, pas seulement le
  premier).

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
  couleur, et partage sa tonalité. Le repos individuel du dernier exercice d'un tour (ou
  du dernier round d'un exercice) est omis quand une récupération le suit immédiatement
  (issue #60, `timer._item_steps(..., include_rest=False)`) : les deux marqueraient
  sinon la même transition deux fois de suite.
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
- Empilée sur mobile, la modale se divise en **deux colonnes à partir de `40rem`**
  (issue #52), pour plus de lisibilité sur grand écran : `.ugg-timer__column-primary`
  (infos de timer, commandes, timeline) et `.ugg-timer__column-secondary` (l'ancien
  « tiers bas », devenu une colonne entière — photo pleine largeur, repères, consignes,
  empilement vertical plutôt que la photo étroite du mobile). Markup et JS inchangés par
  ailleurs : `workout_timer.js` cible des `id`, jamais la structure de leurs parents, ce
  qui a permis d'envelopper sans y toucher.
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
  sens. Le chrono (`.ugg-timer__clock`) et les répétitions (`.ugg-timer__reps`) se lisent
  à bout de bras : 4.25rem / 3rem sur mobile, 6rem / 4rem à partir de `40rem` (issue #58).
- Pendant un repos ou une récupération, c'est l'exercice qui **arrive** qui s'affiche —
  jamais celui qu'on vient de terminer (issue #59) : le libellé en grand
  (`#minuteur-exercice`, préfixé « Suivant : ») **et** le panneau photo/consignes du
  tiers bas (`highlight()`, voir plus haut) pointent tous les deux sur lui, pas
  seulement le texte — la photo restait sinon celle de l'exercice fini, contradiction
  relevée après une première version qui n'avait corrigé que le libellé. `nextWorkStep()`
  cherche le prochain pas de phase `work` dans l'ordre chronologique du minuteur ; un pas
  d'effort affiche son propre exercice, sans préfixe, comme avant.
- Le **tiers bas de l'écran** (`.ugg-timer__current`) reprend l'exercice en cours en
  grand — photo, matériel, muscles principaux — pour s'y référer d'un coup d'œil sans
  chercher la bonne ligne dans la timeline, qui reste au-dessus pour le contexte des pas
  à venir. Alimenté par JavaScript à chaque changement de pas (`highlight()`, dans
  `workout_timer.js`) : il relit la ligne correspondante de la timeline plutôt que de
  dupliquer photo/matériel/muscles dans le JSON du minuteur — une seule source pour ces
  informations. Absent d'exercice sans photo : l'image se masque plutôt que d'afficher
  un cadre vide. La photo s'y affiche entière (`object-fit: contain`, fond neutre en
  lettrboxing, issue #62) — un rognage (`cover`) couperait la posture qu'elle montre ;
  portée volontairement limitée à ce grand panneau, la vignette de la timeline et la
  galerie du catalogue restent en `cover`, un usage différent (aperçu carré). Les
  consignes traduites (repli sur l'anglais) y figurent aussi (issue #63,
  `.ugg-timer__current-instructions`, agrandies à 0.9375rem — issue #67 —, scrollables
  au-delà de 6.5rem plutôt que de faire déborder le panneau sur mobile) — une liste
  cachée par exercice dans la timeline (`.ugg-timer__step-instructions`,
  `timer_timeline.html`) sert de source, clonée par `updateCurrentExercisePanel()`,
  même principe que le nom, le matériel et les muscles. Un exercice qui en compte
  plusieurs les fait défiler toutes les 5 s
  (`startPhotoRotation()`, issue #35 suite) tant que la séance n'est pas en pause — la
  liste complète voyage dans `data-photos` sur la ligne de la timeline (`workouts/
  partials/timer_timeline.html`), séparée par `|`, sur le même principe que
  `data-equipment`/`data-muscles` ; la vignette de la timeline, elle, reste fixe sur la
  première photo. Le nom de l'exercice y est borné à deux lignes (`-webkit-line-clamp`,
  issue #98) et le panneau lui-même défile en dernier recours (`overflow-y: auto`) : un
  nom long ne doit jamais repousser matériel, muscles ou consignes hors de l'écran. La
  photo est bornée par un `max-height` propre plutôt que `height: 100%` du panneau, qui
  n'a pas de hauteur définie — sans quoi elle grandissait ou rétrécissait avec le texte
  voisin au lieu de garder une taille stable.
- Cinq secondes de **préparation**, décomptées avant le premier pas, pour le temps de se
  mettre en place — pas encore comptées dans l'avancement de la séance. Le même sas
  reprend après chaque récupération entre tours/blocs, avant de relancer l'effort
  (issue #61, `runPrep()`/`prepTick()` dans `workout_timer.js`) : redémarrer un tour à
  froid n'est pas plus praticable que démarrer la séance à froid. Toujours hors de
  l'avancement de la séance — la barre reste sur la valeur atteinte à la fin de la
  récupération qui précède, `remaining`/`total` n'étant jamais réassignés pour une
  préparation (`prepRemaining`, une variable dédiée, porte son propre décompte).
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
  l'écran (issue #35 suite), portée par une seule variable `--ugg-timer-phase-color`
  posée sur `.ugg-timer[data-phase="…"]` et reprise par l'étiquette de phase, le chrono
  **et** les répétitions (issue #57 — le gros chrono, plus lisible à distance qu'une
  étiquette, portait encore une couleur neutre) : **préparation** en `--ugg-danger` (on
  démarre, l'urgence du compte à rebours), **effort** dans l'accent de marque
  (`--ugg-accent`, valeur par défaut), **repos** entre exercices en `--ugg-success`, et
  **récupération** entre tours/blocs en `--ugg-info` — seul usage d'une couleur froide
  dans tout le projet, réservé à cette pause pour ne jamais se confondre avec le repos
  entre exercices. La couleur ne fait que renforcer le libellé, jamais le remplacer.
- Le tout dernier exercice du tout dernier tour/circuit ne marque pas son propre
  repos (issue #66, généralisation de #60) : la séance s'arrête juste après, une
  pause n'y servirait à rien de plus qu'après le dernier pas de récupération. Même
  mécanique côté serveur (`workouts.timer.build_timeline`, `omit_rest`) — que le
  format soit interleaved (dernier exercice du dernier tour) ou non (dernier round
  du dernier exercice), avec ou sans récupération configurée.
- L'écran ne s'éteint pas pendant la séance (issue #53) : un verrou d'écran (Screen
  Wake Lock API, `requestWakeLock()`) est posé à l'ouverture du minuteur et relâché à
  sa fermeture, y compris quand l'onglet reprend la main après une perte de visibilité
  (le verrou se relâche alors automatiquement, contrainte de la spec). Le web ne donne
  accès à aucun réglage de luminosité matérielle — c'est l'équivalent le plus proche,
  sur PC comme sur smartphone. Dégradation silencieuse si l'API est absente.
- Un bouton **« Plein écran »** (issue #97) déclenche la vraie Fullscreen API
  (`dialog.requestFullscreen()`) : la modale occupait déjà tout l'écran par CSS mais
  laissait la chrome du navigateur visible. Même posture de dégradation silencieuse que
  le verrou d'écran ci-dessus — le bouton se masque lui-même si l'API est absente ou
  désactivée (iOS Safari, notamment) — et même convention d'état que la bascule favori :
  `aria-pressed` et un libellé qui change (« Plein écran » / « Quitter le plein écran »),
  jamais la seule icône.
- Sur poste de bureau uniquement (`≥ 40rem`, issue #55) : les touches multimédias du
  clavier (Lecture/Pause, Piste suivante) pilotent le minuteur via la Media Session
  API (`setupMediaSession()`), branchées sur les mêmes fonctions que les boutons
  Pause/Passer. Aucune API web ne permet de piloter une application tierce (lecteur de
  musique du système) — barrière de sécurité du navigateur, pas une limite du projet ;
  rien n'est affiché à l'écran, et rien n'est enregistré sur mobile.

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
- Un exercice du **déroulé d'une séance** (`workouts/partials/exercise_item.html`)
  porte la même bascule que sa fiche du catalogue (issue #64) : marquer un favori sans
  quitter la séance pour retrouver l'exercice ailleurs. `item.exercise` doit être
  annoté de `is_favorite` par la vue (`workouts.views._annotate_favorites`, réutilisée
  par `workout_detail` et `workout_exercise_refresh` — ce dernier remplace l'exercice,
  l'état favori doit suivre le remplaçant) ; le partiel n'introduit aucune route
  propre, il réutilise `exercises:toggle_favorite` tel quel.

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
  jamais vers les statiques : le manifeste `collectstatic` est figé à la dernière
  exécution de la commande, avant que ces fichiers n'existent.
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

### Traiter une ou plusieurs issues GitHub

Sur une demande du type « traite l'issue N » / « traite les issues N à M » :

1. **Lire l'issue** (`gh issue view`) avant toute chose — ne jamais deviner son contenu.
2. **Découper en sous-issues** si elle recouvre plusieurs changements indépendants
   (comme la story #68, ou #77) — une sous-issue par changement livrable et testable
   séparément, jamais une story fourre-tout. Une issue déjà atomique (un bug, un
   changement cohérent) ne se découpe pas artificiellement.
3. **Implémenter chaque sous-tâche dans un commit atomique** qui la référence deux
   fois (titre `(#N)`, corps `Refs #N`) — voir *Commits et suivi des issues*.
4. **Vérifier avant de commiter** : lint (`make lint`), suite de tests
   (`make test`), et pour tout changement visuel ou de flux, une vérification
   manuelle au navigateur (pas seulement les tests).
5. **Commenter l'issue traitée** avec le périmètre livré, les décisions prises et ce
   qui reste ouvert — sans la fermer : elle se ferme au merge, via `Closes #N` dans
   un commit une fois la branche fusionnée dans `main`.
6. **Ne jamais pousser sur le dépôt distant sans demande explicite** — les commits
   restent locaux tant que ce n'est pas demandé.

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
```

`make help` liste les cibles disponibles. Détail de l'installation, de la
configuration et de la mise à jour : `docs/INSTALL.md`.
