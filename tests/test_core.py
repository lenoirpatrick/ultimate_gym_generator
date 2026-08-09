"""Socle : sonde de santé et référentiel visuel."""

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
