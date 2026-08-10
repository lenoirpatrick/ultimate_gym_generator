"""Socle : sonde de santé, navigation principale et référentiel visuel."""

import re

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_healthz_repond_200_quand_la_base_est_joignable(client):
    response = client.get(reverse("core:healthz"))

    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "database": "ok"}


@pytest.mark.django_db
def test_healthz_repond_503_quand_la_base_est_injoignable(client, monkeypatch):
    from django.db import connection

    def boom():
        raise RuntimeError("connexion perdue")

    monkeypatch.setattr(connection, "cursor", boom)

    response = client.get(reverse("core:healthz"))

    assert response.status_code == 503
    assert response.json()["status"] == "unhealthy"


@pytest.mark.django_db
def test_accueil_est_public(client):
    assert client.get(reverse("core:home")).status_code == 200


# --------------------------------------------------------------------------- #
# Navigation principale (issue #23)
# --------------------------------------------------------------------------- #


def entetes_de_menu(content: str) -> list[str]:
    """Intitulés des groupes rendus dans le tiroir, dans l'ordre."""
    return re.findall(r'<p class="ugg-nav__heading">\s*([^<]+?)\s*</p>', content)


def test_le_menu_groupe_la_navigation_et_la_configuration(logged_client):
    content = logged_client.get(reverse("core:home")).content.decode()

    assert entetes_de_menu(content) == ["Navigation", "Utilisateur"]


def test_le_groupe_admin_n_apparait_que_pour_le_personnel(staff_client):
    content = staff_client.get(reverse("core:home")).content.decode()

    assert entetes_de_menu(content) == ["Navigation", "Admin", "Utilisateur"]
    assert reverse("aiproviders:list") in content
    assert reverse("accounts:user_list") in content


def test_un_groupe_vide_n_est_pas_titre(logged_client):
    """Un intitulé « Admin » sans rien dessous ferait croire à un droit manquant."""
    content = logged_client.get(reverse("core:home")).content.decode()

    assert "Admin" not in entetes_de_menu(content)
    assert reverse("accounts:user_list") not in content


def test_les_entrees_quotidiennes_sont_rendues_en_barre_et_dans_le_tiroir(logged_client):
    """Une seule description, deux rendus : voir core/nav.py."""
    content = logged_client.get(reverse("core:home")).content.decode()

    assert content.count(reverse("workouts:list")) == 2
    assert "ugg-nav__group--bar" in content
    assert "ugg-nav__group--drawer" in content


def test_l_ecran_courant_est_marque(logged_client):
    content = logged_client.get(reverse("exercises:list")).content.decode()

    assert content.count('aria-current="page"') == 2


@pytest.mark.django_db
def test_le_menu_ne_s_affiche_pas_sans_authentification(client):
    content = client.get(reverse("core:home")).content.decode()

    assert "ugg-nav__panel" not in content
    assert reverse("accounts:login") in content


@pytest.mark.django_db
def test_style_guide_est_masque_hors_debug(client, settings):
    settings.DEBUG = False
    assert client.get(reverse("core:style_guide")).status_code == 404


@pytest.mark.django_db
def test_style_guide_expose_les_trois_spinners_en_debug(client, settings):
    settings.DEBUG = True

    content = client.get(reverse("core:style_guide")).content.decode()

    for variant in ("dumbbell", "kettlebell", "runner"):
        assert f"ugg-spinner--{variant}" in content
