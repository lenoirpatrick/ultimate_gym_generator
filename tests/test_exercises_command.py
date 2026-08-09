"""Commande `load_exercises` : chargement du catalogue hors interface."""

import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from exercises.models import Exercise

pytestmark = pytest.mark.django_db

TOTAL = 4


def executer(*args) -> str:
    sortie = StringIO()
    call_command("load_exercises", *args, stdout=sortie)
    return sortie.getvalue()


@pytest.mark.empty_catalog
def test_la_commande_charge_le_catalogue():
    sortie = executer()

    assert Exercise.objects.count() == TOTAL
    assert f"{TOTAL} exercices chargés" in sortie


def test_la_commande_ne_recharge_pas_un_catalogue_complet():
    """Elle tourne à chaque déploiement : elle doit être sans effet quand tout est là."""
    sortie = executer()

    assert "Rien à faire" in sortie


def test_l_option_force_reimporte_malgre_tout():
    Exercise.objects.filter(slug="Barbell_Squat").update(name="Nom obsolète")

    executer("--force")

    assert Exercise.objects.get(slug="Barbell_Squat").name == "Barbell Squat"


@pytest.mark.empty_catalog
def test_une_source_absente_fait_echouer_la_commande(settings, tmp_path):
    """Un déploiement doit s'arrêter net plutôt que démarrer sans catalogue."""
    settings.EXERCISES_SOURCE = str(tmp_path / "introuvable.json")

    with pytest.raises(CommandError, match="introuvable"):
        executer("--force")


@pytest.mark.empty_catalog
def test_une_source_vide_ne_fait_pas_echouer_la_commande(settings, tmp_path):
    """Rien à charger n'est pas une erreur — et surtout pas un amorçage sans fin."""
    source = tmp_path / "vide.json"
    source.write_text(json.dumps([]), encoding="utf-8")
    settings.EXERCISES_SOURCE = str(source)

    executer()

    assert Exercise.objects.count() == 0


@pytest.mark.empty_catalog
def test_une_source_vide_n_immobilise_pas_l_ecran_de_chargement(settings, tmp_path, logged_client):
    from django.urls import reverse

    source = tmp_path / "vide.json"
    source.write_text(json.dumps([]), encoding="utf-8")
    settings.EXERCISES_SOURCE = str(source)

    response = logged_client.get(reverse("exercises:loading"))

    assert response.status_code == 302
    assert response.url == reverse("core:home")
