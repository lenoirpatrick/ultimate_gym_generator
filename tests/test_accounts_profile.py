"""Profil : édition en libre-service et dépôt d'avatar."""

import io
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

PROFILE_PAYLOAD = {
    "first_name": "Alex",
    "last_name": "Martin",
    "email": "alex@example.test",
    "gender": "F",
    "height_cm": "172",
    "weight_kg": "64.5",
}


def image_file(name: str = "avatar.png", size: tuple[int, int] = (64, 64)) -> SimpleUploadedFile:
    buffer = io.BytesIO()
    Image.new("RGB", size, (190, 227, 25)).save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


@pytest.mark.django_db
def test_le_profil_exige_une_authentification(client):
    response = client.get(reverse("accounts:profile"))

    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


@pytest.mark.django_db
def test_l_utilisateur_enregistre_ses_mesures(logged_client, user):
    logged_client.post(reverse("accounts:profile"), PROFILE_PAYLOAD)

    user.refresh_from_db()
    assert user.height_cm == 172
    assert user.weight_kg == Decimal("64.5")
    assert user.gender == "F"
    assert user.bmi == Decimal("21.8")


@pytest.mark.django_db
def test_une_taille_hors_bornes_est_refusee_par_le_formulaire(logged_client, user):
    response = logged_client.post(
        reverse("accounts:profile"), PROFILE_PAYLOAD | {"height_cm": "400"}
    )

    assert response.status_code == 200
    user.refresh_from_db()
    assert user.height_cm is None


@pytest.mark.django_db
def test_l_utilisateur_depose_un_avatar(logged_client, user):
    logged_client.post(
        reverse("accounts:profile"), PROFILE_PAYLOAD | {"avatar": image_file()}, format="multipart"
    )

    user.refresh_from_db()
    assert user.avatar
    assert f"avatars/{user.pk}/" in user.avatar.name

    user.avatar.delete(save=True)


@pytest.mark.django_db
def test_un_avatar_trop_lourd_est_refuse(logged_client, user, settings):
    settings.MAX_AVATAR_BYTES = 100  # 100 octets : toute vraie image dépasse

    response = logged_client.post(
        reverse("accounts:profile"), PROFILE_PAYLOAD | {"avatar": image_file()}
    )

    assert response.status_code == 200
    assert "trop lourde" in response.content.decode()
    user.refresh_from_db()
    assert not user.avatar


@pytest.mark.django_db
def test_l_utilisateur_ne_peut_pas_se_donner_les_droits_par_le_profil(logged_client, user):
    """Le formulaire de profil n'expose pas is_staff : une tentative reste sans effet."""
    logged_client.post(reverse("accounts:profile"), PROFILE_PAYLOAD | {"is_staff": "on"})

    user.refresh_from_db()
    assert user.is_staff is False


@pytest.mark.django_db
def test_l_utilisateur_change_son_mot_de_passe(logged_client, user):
    response = logged_client.post(
        reverse("accounts:password_change"),
        {
            "old_password": "entrainement-42",
            "new_password1": "haltere-longue-portee-77",
            "new_password2": "haltere-longue-portee-77",
        },
    )

    assert response.status_code == 302
    user.refresh_from_db()
    assert user.check_password("haltere-longue-portee-77")
