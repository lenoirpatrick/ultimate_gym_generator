"""Gestion multi-utilisateurs et inscription libre."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()

NEW_ACCOUNT = {
    "email": "recrue@example.test",
    "first_name": "Sam",
    "last_name": "Durand",
    "password1": "developpe-couche-88-kg",
    "password2": "developpe-couche-88-kg",
}


# --------------------------------------------------------------------------- #
# Accès
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
@pytest.mark.parametrize("route", ["accounts:user_list", "accounts:user_create"])
def test_la_gestion_des_comptes_est_reservee_au_personnel(logged_client, route):
    response = logged_client.get(reverse(route))

    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


@pytest.mark.django_db
def test_le_personnel_voit_la_liste_des_comptes(staff_client, user):
    content = staff_client.get(reverse("accounts:user_list")).content.decode()

    assert user.email in content


# --------------------------------------------------------------------------- #
# Création et modification
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_le_personnel_cree_un_compte(staff_client):
    response = staff_client.post(reverse("accounts:user_create"), NEW_ACCOUNT)

    assert response.status_code == 302
    created = User.objects.get(email="recrue@example.test")
    assert created.is_staff is False
    assert created.is_active is True


@pytest.mark.django_db
def test_le_personnel_desactive_un_compte(staff_client, user):
    staff_client.post(
        reverse("accounts:user_update", args=[user.pk]),
        {
            "email": user.email,
            "first_name": "",
            "last_name": "",
            "gender": "N",
            "height_cm": "",
            "weight_kg": "",
            "is_active": "",
            "is_staff": "",
        },
    )

    user.refresh_from_db()
    assert user.is_active is False


@pytest.mark.django_db
def test_le_personnel_ne_peut_pas_se_retirer_ses_propres_droits(staff_client, staff):
    """Se désactiver ou se déclasser pourrait laisser l'installation sans administrateur."""
    staff_client.post(
        reverse("accounts:user_update", args=[staff.pk]),
        {
            "email": staff.email,
            "first_name": "",
            "last_name": "",
            "gender": "N",
            "height_cm": "",
            "weight_kg": "",
            "is_active": "",
            "is_staff": "",
        },
    )

    staff.refresh_from_db()
    assert staff.is_staff is True
    assert staff.is_active is True


@pytest.mark.django_db
def test_un_compte_inexistant_renvoie_404(staff_client):
    assert staff_client.get(reverse("accounts:user_update", args=[999_999])).status_code == 404


# --------------------------------------------------------------------------- #
# Inscription libre
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_l_inscription_libre_est_desactivee_par_defaut(client, settings):
    assert settings.ALLOW_SELF_REGISTRATION is False
    assert client.get(reverse("accounts:register")).status_code == 404


@pytest.mark.django_db
def test_la_page_de_connexion_ne_propose_pas_l_inscription_par_defaut(client):
    content = client.get(reverse("accounts:login")).content.decode()

    assert reverse("accounts:register") not in content


@pytest.mark.django_db
def test_l_inscription_libre_cree_un_compte_ordinaire_quand_elle_est_ouverte(client, settings):
    settings.ALLOW_SELF_REGISTRATION = True

    response = client.post(reverse("accounts:register"), NEW_ACCOUNT)

    assert response.status_code == 302
    created = User.objects.get(email="recrue@example.test")
    assert created.is_staff is False
    assert created.is_superuser is False
