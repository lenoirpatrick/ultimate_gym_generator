"""Conseils rédigés par l'IA : habillage d'une séance, jamais une dépendance."""

import pytest
from django.urls import reverse

from aiproviders.clients import ProviderError
from aiproviders.models import ProviderCredential
from workouts import coaching
from workouts.models import Workout

pytestmark = pytest.mark.django_db

NOTES = "Garde le dos gainé.\n\nSouffle à l'effort."


@pytest.fixture
def workout(logged_client, user):
    logged_client.post(
        reverse("workouts:create"),
        {"duration_minutes": "20", "workout_format": "tabata", "favorites_ratio": "0"},
    )
    return Workout.objects.get(user=user)


def stub_provider(monkeypatch, generate):
    monkeypatch.setattr(
        "workouts.coaching.get_active_client",
        lambda: type("Stub", (), {"generate": generate})(),
    )


# --------------------------------------------------------------------------- #
# Sélection du fournisseur
# --------------------------------------------------------------------------- #


def test_aucun_fournisseur_configure_ne_donne_aucun_client():
    from aiproviders.clients import get_active_client

    assert get_active_client() is None


def test_un_fournisseur_inactif_est_ignore():
    """Décocher « actif » doit suffire à couper les appels."""
    from aiproviders.clients import get_active_client

    ProviderCredential.objects.create(provider="anthropic", secret="sk-test", is_active=False)

    assert get_active_client() is None


def test_un_fournisseur_sans_cle_est_ignore():
    from aiproviders.clients import get_active_client

    ProviderCredential.objects.create(provider="anthropic", secret="", is_active=True)

    assert get_active_client() is None


def test_le_premier_fournisseur_utilisable_est_retenu():
    from aiproviders.clients import get_active_client

    ProviderCredential.objects.create(provider="mistral", secret="cle", is_active=True)
    ProviderCredential.objects.create(provider="anthropic", secret="sk-test", is_active=True)

    # L'ordre est celui du registre, où Anthropic précède Mistral.
    assert get_active_client().credential.provider == "anthropic"


# --------------------------------------------------------------------------- #
# Rédaction
# --------------------------------------------------------------------------- #


def test_les_conseils_sont_enregistres(workout, monkeypatch):
    """Mémorisés, sinon chaque consultation rappellerait — et repaierait — le fournisseur."""
    stub_provider(monkeypatch, lambda self, prompt, **kwargs: NOTES)

    assert coaching.write_notes(workout) == NOTES

    workout.refresh_from_db()
    assert workout.coaching_notes == NOTES


def test_des_conseils_deja_ecrits_ne_sont_pas_redemandes(workout, monkeypatch):
    workout.coaching_notes = "Déjà rédigé."
    workout.save()

    def refuser(self, prompt, **kwargs):
        raise AssertionError("le fournisseur ne doit pas être appelé")

    stub_provider(monkeypatch, refuser)

    assert coaching.write_notes(workout) == "Déjà rédigé."


def test_la_seance_est_decrite_au_fournisseur(workout, monkeypatch):
    captured = {}

    def capturer(self, prompt, **kwargs):
        captured["prompt"] = prompt
        return NOTES

    stub_provider(monkeypatch, capturer)
    coaching.write_notes(workout)

    assert "Tabata" in captured["prompt"]
    assert "20s d'effort" in captured["prompt"]
    assert workout.items.first().exercise.name in captured["prompt"]


def test_sans_fournisseur_aucun_conseil_mais_aucune_erreur(workout, monkeypatch):
    monkeypatch.setattr("workouts.coaching.get_active_client", lambda: None)

    assert coaching.write_notes(workout) == ""


def test_une_panne_du_fournisseur_ne_remonte_pas(workout, monkeypatch):
    """L'utilisateur n'a que faire d'une erreur de fournisseur devant une séance prête."""

    def tomber(self, prompt, **kwargs):
        raise ProviderError("Quota dépassé.")

    stub_provider(monkeypatch, tomber)

    assert coaching.write_notes(workout) == ""
    workout.refresh_from_db()
    assert workout.coaching_notes == ""


def test_une_reponse_vide_n_est_pas_enregistree(workout, monkeypatch):
    stub_provider(monkeypatch, lambda self, prompt, **kwargs: "   ")

    assert coaching.write_notes(workout) == ""


# --------------------------------------------------------------------------- #
# Affichage
# --------------------------------------------------------------------------- #


def test_la_seance_demande_les_conseils_en_differe(logged_client, workout):
    content = logged_client.get(reverse("workouts:detail", args=[workout.pk])).content.decode()

    assert reverse("workouts:coaching", args=[workout.pk]) in content
    assert 'hx-trigger="load"' in content
    # Règle graphique : icône de sport animée pendant l'attente.
    assert "ugg-spinner--dumbbell" in content


def test_le_fragment_rend_les_conseils(logged_client, workout, monkeypatch):
    stub_provider(monkeypatch, lambda self, prompt, **kwargs: NOTES)

    content = logged_client.get(reverse("workouts:coaching", args=[workout.pk])).content.decode()

    assert "Conseils du coach" in content
    assert "Garde le dos gainé." in content


def test_le_fragment_reste_muet_sans_conseil(logged_client, workout, monkeypatch):
    """Pas d'alerte d'erreur devant une séance qui, elle, est prête."""
    monkeypatch.setattr("workouts.coaching.get_active_client", lambda: None)

    content = logged_client.get(reverse("workouts:coaching", args=[workout.pk])).content.decode()

    assert "Conseils du coach" not in content
    assert content.strip() == ""


def test_les_conseils_d_un_autre_utilisateur_sont_introuvables(staff_client, workout):
    response = staff_client.get(reverse("workouts:coaching", args=[workout.pk]))

    assert response.status_code == 404


def test_la_seance_reste_complete_sans_fournisseur(logged_client, workout):
    """Aucun fournisseur configuré : le déroulé doit être là quand même."""
    content = logged_client.get(reverse("workouts:detail", args=[workout.pk])).content.decode()

    assert "Bloc 1" in content
    assert workout.items.count() > 0
