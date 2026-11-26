"""Rechargement du référentiel à la demande, hors du premier amorçage (issue #29)."""

import pytest
from django.urls import reverse

from aiproviders.models import ProviderCredential
from exercises import catalog
from exercises.models import Exercise

pytestmark = pytest.mark.django_db

TOTAL = 4


# --------------------------------------------------------------------------- #
# Accès
# --------------------------------------------------------------------------- #


def test_la_page_exige_une_authentification(client):
    response = client.get(reverse("exercises:reload"))

    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


def test_un_utilisateur_ordinaire_ne_peut_pas_recharger(logged_client):
    """Recharger avec traduction consomme des jetons IA : réservé au personnel."""
    response = logged_client.get(reverse("exercises:reload"))

    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


def test_le_personnel_accede_a_l_ecran(staff_client):
    assert staff_client.get(reverse("exercises:reload")).status_code == 200


def test_le_lot_est_reserve_au_personnel(logged_client):
    response = logged_client.post(reverse("exercises:reload_batch"), {"offset": 0})

    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


def test_le_lot_refuse_la_methode_get(staff_client):
    assert staff_client.get(reverse("exercises:reload_batch")).status_code == 405


# --------------------------------------------------------------------------- #
# Bandeau IA
# --------------------------------------------------------------------------- #


def test_sans_fournisseur_seul_un_rechargement_simple_est_propose(staff_client):
    content = staff_client.get(reverse("exercises:reload")).content.decode()

    assert "Aucun fournisseur IA actif" in content
    assert "Recharger avec traduction" not in content
    assert "Recharger le référentiel" in content


def test_avec_un_fournisseur_le_bandeau_le_nomme(staff_client):
    ProviderCredential.objects.create(
        provider="claude_gateway",
        secret="jeton",
        base_url="http://passerelle.test:8765",
        default_model="opus",
        is_active=True,
    )

    content = staff_client.get(reverse("exercises:reload")).content.decode()

    assert "Claude Gateway" in content
    assert "(opus)" in content
    assert "consommer des jetons IA" in content
    assert "Recharger avec traduction" in content
    assert "Recharger sans traduction" in content


# --------------------------------------------------------------------------- #
# Progression
# --------------------------------------------------------------------------- #


def test_lecran_annonce_le_volume_du_referentiel(staff_client):
    content = staff_client.get(reverse("exercises:reload")).content.decode()

    assert str(TOTAL) in content


def test_un_lot_complet_signale_le_referentiel_a_jour(staff_client):
    content = staff_client.post(
        reverse("exercises:reload_batch"), {"offset": 0, "translate": "0"}
    ).content.decode()

    assert 'aria-valuenow="100"' in content
    assert "Référentiel à jour" in content
    assert Exercise.objects.count() == TOTAL


def test_un_lot_non_final_reclame_le_suivant(staff_client, monkeypatch):
    monkeypatch.setattr(catalog, "BATCH_SIZE", 2)

    content = staff_client.post(
        reverse("exercises:reload_batch"), {"offset": 0, "translate": "0"}
    ).content.decode()

    assert 'aria-valuenow="50"' in content
    assert reverse("exercises:reload_batch") in content
    assert '"offset": 2' in content


def test_le_referentiel_deja_charge_ne_bloque_pas_le_rechargement(staff_client):
    """Contrairement à l'amorçage, le compte de lignes est déjà complet dès le départ."""
    assert Exercise.objects.count() == TOTAL

    content = staff_client.post(
        reverse("exercises:reload_batch"), {"offset": 0, "translate": "0"}
    ).content.decode()

    assert 'aria-valuenow="100"' in content


def test_la_traduction_se_propage_d_un_lot_a_l_autre(staff_client, monkeypatch):
    monkeypatch.setattr(catalog, "BATCH_SIZE", 2)

    content = staff_client.post(
        reverse("exercises:reload_batch"), {"offset": 0, "translate": "1"}
    ).content.decode()

    assert '"translate": "1"' in content


# --------------------------------------------------------------------------- #
# Traduction fiche par fiche (issue #152)
# --------------------------------------------------------------------------- #

#: Fiches du catalogue de test qui ont des consignes (la quatrième n'en a pas).
A_TRADUIRE = 3


def traduire_avec(monkeypatch, reponse):
    """Remplace l'appel IA : `reponse` est une liste, ou une exception à lever."""
    appels = []

    def traduire(instructions):
        appels.append(instructions)
        if isinstance(reponse, Exception):
            raise reponse
        return reponse

    monkeypatch.setattr(catalog.translation, "translate_or_raise", traduire)
    return appels


def etape(staff_client, **etat):
    etat.setdefault("total", A_TRADUIRE)
    return staff_client.post(reverse("exercises:translate_batch"), etat).content.decode()


def test_le_dernier_lot_avec_traduction_ouvre_la_phase_de_traduction(staff_client, monkeypatch):
    """Aucun appel IA dans un lot : la traduction suit, une fiche à la fois."""
    appels = traduire_avec(monkeypatch, ["Traduit."])

    content = staff_client.post(
        reverse("exercises:reload_batch"), {"offset": 0, "translate": "1"}
    ).content.decode()

    assert appels == []
    assert f"{TOTAL} exercices synchronisés" in content
    assert f"0 / {A_TRADUIRE} fiches" in content
    assert 'aria-valuenow="0"' in content
    assert reverse("exercises:translate_batch") in content
    assert 'hx-trigger="load"' in content


def test_chaque_requete_traduit_une_seule_fiche(staff_client, monkeypatch):
    appels = traduire_avec(monkeypatch, ["Traduit."])
    premiere = catalog.untranslated().first()

    content = etape(staff_client, processed=0, after=0)

    assert len(appels) == 1
    assert f"1 / {A_TRADUIRE} fiches" in content
    assert 'aria-valuenow="33"' in content
    assert f"Traduite : {premiere.name}" in content
    # La requête suivante repart de la fiche traitée.
    assert f'"after": {premiere.pk}' in content
    assert 'hx-trigger="load"' in content


def test_la_fiche_traduite_est_enregistree(staff_client, monkeypatch):
    traduire_avec(monkeypatch, ["Traduit un.", "Traduit deux.", "Traduit trois."])

    etape(staff_client, processed=0, after=0)

    assert Exercise.objects.get(slug="Barbell_Squat").instructions_fr == [
        "Traduit un.",
        "Traduit deux.",
        "Traduit trois.",
    ]


def test_la_derniere_fiche_termine_la_traduction(staff_client, monkeypatch):
    traduire_avec(monkeypatch, ["Traduit."])
    derniere = catalog.untranslated().last()

    content = etape(staff_client, processed=A_TRADUIRE - 1, after=derniere.pk - 1)

    assert 'aria-valuenow="100"' in content
    assert "Traduction terminée" in content
    assert f"{A_TRADUIRE} fiches traduites" in content
    assert 'hx-trigger="load"' not in content


def test_plus_rien_a_traduire_termine_sans_appel(staff_client, monkeypatch):
    appels = traduire_avec(monkeypatch, ["Traduit."])
    derniere = catalog.untranslated().last()

    content = etape(staff_client, processed=1, after=derniere.pk)

    assert appels == []
    assert "Traduction terminée" in content


def test_un_referentiel_deja_traduit_le_dit(staff_client, monkeypatch):
    Exercise.objects.exclude(instructions=[]).update(instructions_fr=["Déjà traduit."])
    traduire_avec(monkeypatch, ["Traduit."])

    content = staff_client.post(
        reverse("exercises:reload_batch"), {"offset": 0, "translate": "1"}
    ).content.decode()

    assert "Toutes les fiches sont déjà traduites" in content
    assert reverse("exercises:translate_batch") not in content


def test_un_echec_est_compte_et_la_traduction_continue(staff_client, monkeypatch):
    traduire_avec(monkeypatch, catalog.translation.TranslationError("Passerelle occupée."))

    content = etape(staff_client, processed=0, after=0)

    assert "1 échec jusqu" in content
    assert "Échec sur" in content
    assert '"failed": 1' in content
    assert '"streak": 1' in content
    assert 'hx-trigger="load"' in content


def test_une_fiche_en_echec_n_est_pas_reprise_en_boucle(staff_client, monkeypatch):
    """Avancer par clé : la fiche suivante est tentée, pas la même indéfiniment."""
    appels = traduire_avec(monkeypatch, catalog.translation.TranslationError("Illisible."))
    premiere, seconde = list(catalog.untranslated()[:2])

    etape(staff_client, processed=1, failed=1, streak=1, after=premiere.pk)

    assert appels == [seconde.instructions]


def test_des_echecs_en_serie_interrompent_la_traduction(staff_client, monkeypatch):
    traduire_avec(monkeypatch, catalog.translation.TranslationError("Jeton refusé."))
    total = 10

    content = etape(staff_client, total=total, processed=2, failed=2, streak=2, after=0)

    assert "Traduction interrompue" in content
    assert "Jeton refusé." in content
    assert "Reprendre la traduction" in content
    # Plus aucune requête automatique : on attend une décision.
    assert 'hx-trigger="load"' not in content


def test_reprendre_apres_interruption_repart_sur_une_serie_neuve(staff_client, monkeypatch):
    traduire_avec(monkeypatch, ["Traduit."])

    content = etape(staff_client, total=10, processed=3, failed=3, streak=3, after=0)

    assert '"streak": 0' in content
    assert "Traduction interrompue" not in content


def test_un_etat_forge_ne_fausse_pas_la_barre(staff_client, monkeypatch):
    """Le total voyage dans la requête : il ne peut pas descendre sous le traité."""
    traduire_avec(monkeypatch, ["Traduit."])

    content = etape(staff_client, total=0, processed="abc", failed=99, after=-5)

    assert 'aria-valuenow="100"' in content


def test_la_traduction_est_reservee_au_personnel(logged_client):
    response = logged_client.post(reverse("exercises:translate_batch"), {"total": 1})

    assert response.status_code == 302


def test_la_traduction_refuse_la_methode_get(staff_client):
    assert staff_client.get(reverse("exercises:translate_batch")).status_code == 405


def test_l_ecran_annonce_le_nombre_de_fiches_a_traduire(staff_client):
    ProviderCredential.objects.create(provider="gemini", secret="cle", is_active=True)

    content = staff_client.get(reverse("exercises:reload")).content.decode()

    assert f"{A_TRADUIRE} fiches à traduire, une par une" in content


def test_une_source_illisible_est_annoncee_sans_bloquer(staff_client, settings, tmp_path):
    settings.EXERCISES_SOURCE = str(tmp_path / "introuvable.json")

    content = staff_client.post(
        reverse("exercises:reload_batch"), {"offset": 0, "translate": "0"}
    ).content.decode()

    assert "introuvable" in content
