"""Premier démarrage : une installation sans compte doit pouvoir en créer un."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()

FIRST_ACCOUNT = {
    "email": "coach@example.test",
    "first_name": "Alex",
    "last_name": "Martin",
    "password1": "brique-poulie-45-kg",
    "password2": "brique-poulie-45-kg",
}


@pytest.mark.fresh_install
@pytest.mark.django_db
@pytest.mark.parametrize("route", ["core:home", "accounts:login", "aiproviders:list"])
def test_sans_compte_toute_page_mene_a_la_creation(client, route):
    response = client.get(reverse(route))

    assert response.status_code == 302
    assert response.url == reverse("accounts:first_run")


@pytest.mark.fresh_install
@pytest.mark.django_db
def test_la_sonde_de_sante_reste_joignable_sans_compte(client):
    """Un orchestrateur doit pouvoir sonder l'application avant son amorçage."""
    assert client.get(reverse("core:healthz")).status_code == 200


@pytest.mark.fresh_install
@pytest.mark.django_db
def test_le_premier_compte_est_administrateur_et_connecte(client):
    response = client.post(reverse("accounts:first_run"), FIRST_ACCOUNT, follow=True)

    created = User.objects.get(email="coach@example.test")
    assert created.is_staff is True
    assert created.is_superuser is True
    assert response.context["user"].is_authenticated
    assert response.request["PATH_INFO"] == reverse("core:home")


@pytest.mark.fresh_install
@pytest.mark.django_db
def test_un_mot_de_passe_trop_faible_est_refuse(client):
    payload = FIRST_ACCOUNT | {"password1": "1234", "password2": "1234"}

    response = client.post(reverse("accounts:first_run"), payload)

    assert response.status_code == 200
    assert User.objects.count() == 0


@pytest.mark.django_db
def test_l_ecran_disparait_une_fois_un_compte_cree(client):
    """L'amorçage ne doit pas rester une porte ouverte."""
    response = client.get(reverse("accounts:first_run"))

    assert response.status_code == 302
    assert response.url == reverse("core:home")


@pytest.mark.django_db
def test_l_ecran_refuse_de_creer_un_second_compte(client):
    avant = User.objects.count()

    client.post(reverse("accounts:first_run"), FIRST_ACCOUNT)

    assert User.objects.count() == avant
