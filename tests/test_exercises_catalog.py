"""Import du catalogue : fidélité des données, idempotence, découpage en lots."""

import json

import pytest

from exercises import catalog
from exercises.models import Exercise, Muscle

pytestmark = pytest.mark.django_db

# La source de test contient 4 exercices — voir tests/fixtures/exercises.json.
TOTAL = 4


# --------------------------------------------------------------------------- #
# Fidélité des données importées
# --------------------------------------------------------------------------- #


def test_le_catalogue_est_charge_en_entier():
    assert Exercise.objects.count() == TOTAL


def test_un_exercice_conserve_ses_attributs():
    squat = Exercise.objects.get(slug="Barbell_Squat")

    assert squat.name == "Barbell Squat"
    assert squat.category == Exercise.Category.STRENGTH
    assert squat.level == Exercise.Level.BEGINNER
    assert squat.force == Exercise.Force.PUSH
    assert squat.mechanic == Exercise.Mechanic.COMPOUND
    assert squat.equipment == Exercise.Equipment.BARBELL
    assert len(squat.instructions) == 3
    assert squat.images == ["Barbell_Squat/0.jpg", "Barbell_Squat/1.jpg"]


def test_les_muscles_sont_rattaches_par_role():
    squat = Exercise.objects.get(slug="Barbell_Squat")

    assert [m.slug for m in squat.primary_muscles.all()] == ["quadriceps"]
    assert sorted(m.slug for m in squat.secondary_muscles.all()) == ["glutes", "hamstrings"]


def test_les_muscles_portent_un_libelle_francais():
    assert Muscle.objects.get(slug="hamstrings").name == "Ischio-jambiers"


def test_un_champ_absent_de_la_source_reste_vide():
    """Une trentaine d'exercices n'ont ni type d'effort ni matériel déclaré."""
    etirement = Exercise.objects.get(slug="Calf_Stretch")

    assert etirement.force == ""
    assert etirement.mechanic == ""
    assert etirement.equipment == ""
    assert etirement.secondary_muscles.count() == 0


def test_un_exercice_sans_muscle_ni_consigne_est_accepte():
    minimal = Exercise.objects.get(slug="Text_Only_Exercise")

    assert minimal.instructions == []
    assert minimal.images == []
    assert minimal.primary_muscles.count() == 0


def test_le_catalogue_se_filtre_par_muscle_et_materiel():
    """C'est l'usage que fera la génération de programmes."""
    trouves = Exercise.objects.filter(primary_muscles__slug="chest", equipment="dumbbell")

    assert [e.slug for e in trouves] == ["Dumbbell_Bench_Press"]


# --------------------------------------------------------------------------- #
# Idempotence
# --------------------------------------------------------------------------- #


def test_un_second_import_ne_duplique_rien():
    catalog.import_all()

    assert Exercise.objects.count() == TOTAL
    assert Muscle.objects.get(slug="quadriceps").exercises_as_primary.count() == 1


def test_un_second_import_met_a_jour_les_fiches_existantes():
    Exercise.objects.filter(slug="Barbell_Squat").update(name="Nom obsolète")

    catalog.import_all()

    assert Exercise.objects.get(slug="Barbell_Squat").name == "Barbell Squat"


# --------------------------------------------------------------------------- #
# Découpage en lots
# --------------------------------------------------------------------------- #


@pytest.mark.empty_catalog
def test_un_lot_n_importe_que_sa_tranche():
    atteint = catalog.import_batch(offset=0, size=2)

    assert atteint == 2
    assert Exercise.objects.count() == 2


@pytest.mark.empty_catalog
def test_les_lots_successifs_couvrent_tout_le_catalogue():
    offset = 0
    while offset < TOTAL:
        offset = catalog.import_batch(offset, size=2)

    assert offset == TOTAL
    assert Exercise.objects.count() == TOTAL


@pytest.mark.empty_catalog
def test_un_offset_au_dela_de_la_source_ne_fait_rien():
    assert catalog.import_batch(offset=9999) == TOTAL
    assert Exercise.objects.count() == 0


@pytest.mark.empty_catalog
def test_la_progression_se_mesure_sur_la_base():
    assert catalog.progress() == catalog.Progress(imported=0, total=TOTAL)
    assert catalog.is_loaded() is False

    catalog.import_batch(offset=0, size=2)

    progression = catalog.progress()
    assert progression.imported == 2
    assert progression.percent == 50
    assert progression.done is False


def test_le_catalogue_complet_est_signale_comme_charge():
    assert catalog.is_loaded() is True
    assert catalog.progress().percent == 100


# --------------------------------------------------------------------------- #
# Source absente ou illisible
# --------------------------------------------------------------------------- #


@pytest.mark.empty_catalog
def test_une_source_absente_donne_un_message_actionnable(settings, tmp_path):
    settings.EXERCISES_SOURCE = str(tmp_path / "introuvable.json")

    with pytest.raises(catalog.CatalogError, match="introuvable"):
        catalog.entries()


@pytest.mark.empty_catalog
def test_une_source_illisible_est_signalee(settings, tmp_path):
    source = tmp_path / "casse.json"
    source.write_text("{ pas du json", encoding="utf-8")
    settings.EXERCISES_SOURCE = str(source)

    with pytest.raises(catalog.CatalogError, match="illisible"):
        catalog.entries()


@pytest.mark.empty_catalog
def test_une_source_qui_n_est_pas_une_liste_est_refusee(settings, tmp_path):
    source = tmp_path / "objet.json"
    source.write_text(json.dumps({"exercices": []}), encoding="utf-8")
    settings.EXERCISES_SOURCE = str(source)

    with pytest.raises(catalog.CatalogError, match="liste"):
        catalog.entries()


@pytest.mark.empty_catalog
def test_sans_source_lisible_l_application_n_est_pas_bloquee(settings, tmp_path):
    """Un amorçage impossible ne doit pas enfermer l'utilisateur sur l'écran de chargement."""
    settings.EXERCISES_SOURCE = str(tmp_path / "introuvable.json")

    assert catalog.is_loaded() is True


@pytest.mark.empty_catalog
def test_un_muscle_inconnu_de_la_traduction_est_conserve(settings, tmp_path):
    """Une source ultérieure peut introduire un groupe musculaire : il ne doit pas être perdu."""
    source = tmp_path / "nouveau.json"
    source.write_text(
        json.dumps(
            [
                {
                    "id": "Grip_Crush",
                    "name": "Grip Crush",
                    "category": "strength",
                    "level": "beginner",
                    "primaryMuscles": ["fingers"],
                }
            ]
        ),
        encoding="utf-8",
    )
    settings.EXERCISES_SOURCE = str(source)

    catalog.import_all()

    muscle = Exercise.objects.get(slug="Grip_Crush").primary_muscles.get()
    assert muscle.slug == "fingers"
    assert muscle.name == "fingers"


@pytest.mark.empty_catalog
def test_une_entree_sans_identifiant_est_ignoree(settings, tmp_path):
    """Une ligne inexploitable ne doit pas interrompre l'import des suivantes."""
    source = tmp_path / "bancal.json"
    source.write_text(
        json.dumps(
            [
                {"category": "strength", "level": "beginner"},
                {"id": "Valide", "name": "Valide", "category": "cardio", "level": "beginner"},
            ]
        ),
        encoding="utf-8",
    )
    settings.EXERCISES_SOURCE = str(source)

    catalog.import_all()

    assert [e.slug for e in Exercise.objects.all()] == ["Valide"]


@pytest.mark.empty_catalog
def test_une_source_vide_est_consideree_comme_chargee(settings, tmp_path):
    """Sans exercice à charger, l'amorçage n'a aucune raison de retenir l'utilisateur."""
    source = tmp_path / "vide.json"
    source.write_text("[]", encoding="utf-8")
    settings.EXERCISES_SOURCE = str(source)

    assert catalog.progress().percent == 100
    assert catalog.is_loaded() is True


def test_les_objets_se_nomment_lisiblement():
    assert str(Exercise.objects.get(slug="Barbell_Squat")) == "Barbell Squat"
    assert str(Muscle.objects.get(slug="chest")) == "Pectoraux"


@pytest.mark.empty_catalog
def test_une_valeur_hors_referentiel_est_ecartee(settings, tmp_path):
    """Un niveau inventé ne doit pas entrer en base sous prétexte qu'il est dans la source."""
    source = tmp_path / "exotique.json"
    source.write_text(
        json.dumps(
            [
                {
                    "id": "Mystere",
                    "name": "Mystère",
                    "category": "strength",
                    "level": "beginner",
                    "equipment": "jetpack",
                    "force": "twist",
                }
            ]
        ),
        encoding="utf-8",
    )
    settings.EXERCISES_SOURCE = str(source)

    catalog.import_all()

    mystere = Exercise.objects.get(slug="Mystere")
    assert mystere.equipment == ""
    assert mystere.force == ""


# --------------------------------------------------------------------------- #
# Illustrations vendorées (issue #29)
# --------------------------------------------------------------------------- #


def test_les_illustrations_sont_copiees_vers_le_media(settings, tmp_path):
    source = tmp_path / "source_images"
    (source / "Barbell_Squat").mkdir(parents=True)
    (source / "Barbell_Squat" / "0.jpg").write_bytes(b"jpeg-content")
    settings.EXERCISES_IMAGES_SOURCE = str(source)
    settings.MEDIA_ROOT = str(tmp_path / "media")

    catalog.sync_images(["Barbell_Squat/0.jpg"])

    copie = tmp_path / "media" / "exercises" / "Barbell_Squat" / "0.jpg"
    assert copie.read_bytes() == b"jpeg-content"


def test_une_illustration_deja_copiee_n_est_pas_relue(settings, tmp_path):
    source = tmp_path / "source_images"
    (source / "Barbell_Squat").mkdir(parents=True)
    (source / "Barbell_Squat" / "0.jpg").write_bytes(b"version-recente")
    settings.EXERCISES_IMAGES_SOURCE = str(source)
    settings.MEDIA_ROOT = str(tmp_path / "media")

    destination = tmp_path / "media" / "exercises" / "Barbell_Squat"
    destination.mkdir(parents=True)
    (destination / "0.jpg").write_bytes(b"version-en-place")

    catalog.sync_images(["Barbell_Squat/0.jpg"])

    assert (destination / "0.jpg").read_bytes() == b"version-en-place"


def test_une_illustration_absente_de_la_source_est_ignoree(settings, tmp_path):
    """Les illustrations sont un supplément : leur absence ne doit rien casser."""
    settings.EXERCISES_IMAGES_SOURCE = str(tmp_path / "introuvable")
    settings.MEDIA_ROOT = str(tmp_path / "media")

    catalog.sync_images(["Inconnu/0.jpg"])

    assert not (tmp_path / "media" / "exercises" / "Inconnu").exists()


def test_import_batch_synchronise_les_illustrations_du_lot(settings, tmp_path):
    source = tmp_path / "source_images"
    (source / "Barbell_Squat").mkdir(parents=True)
    (source / "Barbell_Squat" / "0.jpg").write_bytes(b"jpeg-content")
    settings.EXERCISES_IMAGES_SOURCE = str(source)
    settings.MEDIA_ROOT = str(tmp_path / "media")

    catalog.import_all()

    copie = tmp_path / "media" / "exercises" / "Barbell_Squat" / "0.jpg"
    assert copie.exists()


def test_les_adresses_d_illustration_pointent_vers_le_media(settings):
    settings.MEDIA_URL = "/media/"

    squat = Exercise.objects.get(slug="Barbell_Squat")

    assert squat.image_urls == [
        "/media/exercises/Barbell_Squat/0.jpg",
        "/media/exercises/Barbell_Squat/1.jpg",
    ]


# --------------------------------------------------------------------------- #
# Traduction à la demande (issue #29)
# --------------------------------------------------------------------------- #


def stub_translation(monkeypatch, translated):
    monkeypatch.setattr(
        catalog.translation, "translate_instructions", lambda instructions: translated
    )


def test_sans_loption_traduire_les_consignes_restent_en_anglais(monkeypatch):
    def refuser(instructions):
        raise AssertionError("la traduction ne doit pas être demandée sans l'option")

    monkeypatch.setattr(catalog.translation, "translate_instructions", refuser)

    catalog.import_all()

    assert Exercise.objects.get(slug="Barbell_Squat").instructions_fr == []


def test_loption_traduire_enregistre_la_traduction(monkeypatch):
    traduit = ["Traduit un.", "Traduit deux.", "Traduit trois."]
    stub_translation(monkeypatch, traduit)

    catalog.import_all(translate=True)

    assert Exercise.objects.get(slug="Barbell_Squat").instructions_fr == traduit


def test_une_fiche_deja_traduite_n_est_pas_retraduite(monkeypatch):
    squat = Exercise.objects.get(slug="Barbell_Squat")
    squat.instructions_fr = ["Déjà traduit."]
    squat.save()

    demandes = []
    monkeypatch.setattr(
        catalog.translation,
        "translate_instructions",
        lambda instructions: demandes.append(instructions) or ["Traduit."],
    )

    catalog.import_all(translate=True)

    assert squat.instructions not in demandes
    assert Exercise.objects.get(slug="Barbell_Squat").instructions_fr == ["Déjà traduit."]


def test_un_echec_de_traduction_laisse_la_fiche_en_anglais(monkeypatch):
    stub_translation(monkeypatch, None)

    catalog.import_all(translate=True)

    assert Exercise.objects.get(slug="Barbell_Squat").instructions_fr == []


def test_une_fiche_sans_consigne_n_est_pas_envoyee_en_traduction(monkeypatch):
    demandes = []
    monkeypatch.setattr(
        catalog.translation,
        "translate_instructions",
        lambda instructions: demandes.append(instructions) or ["Traduit."],
    )

    catalog.import_all(translate=True)

    assert [] not in demandes
    assert Exercise.objects.get(slug="Text_Only_Exercise").instructions_fr == []
