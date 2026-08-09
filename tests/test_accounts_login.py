"""Connexion : l'adresse e-mail est le seul identifiant accepté."""

import pytest
from django.urls import reverse

PASSWORD = "entrainement-42"


def connexion(client, email: str, password: str = PASSWORD):
    return client.post(
        reverse("accounts:login"),
        {"username": email, "password": password},
        follow=True,
    )


@pytest.mark.django_db
def test_l_ecran_de_connexion_demande_une_adresse_e_mail(client):
    content = client.get(reverse("accounts:login")).content.decode()

    assert "Adresse e-mail" in content
    # Le clavier d'un téléphone doit proposer « @ », et la saisie automatique s'appliquer.
    assert 'type="email"' in content
    assert 'autocomplete="email"' in content


@pytest.mark.django_db
def test_l_adresse_e_mail_et_le_mot_de_passe_ouvrent_la_session(client, user):
    response = connexion(client, user.email)

    assert response.context["user"].is_authenticated
    assert response.request["PATH_INFO"] == reverse("core:home")


@pytest.mark.django_db
def test_la_casse_de_l_adresse_n_empeche_pas_la_connexion(client, user):
    """Un e-mail tapé avec des majuscules reste le même identifiant."""
    response = connexion(client, "COACH@Example.TEST")

    assert response.context["user"].is_authenticated


@pytest.mark.django_db
def test_un_mot_de_passe_faux_ne_revele_pas_l_existence_du_compte(client, user):
    response = connexion(client, user.email, password="mauvais-mot-de-passe")

    assert response.context["user"].is_authenticated is False
    assert "Adresse e-mail ou mot de passe incorrect." in response.content.decode()


@pytest.mark.django_db
def test_une_adresse_inconnue_donne_le_meme_message(client):
    """Un message distinct permettrait d'énumérer les comptes de l'installation."""
    response = connexion(client, "inconnu@example.test")

    assert response.context["user"].is_authenticated is False
    assert "Adresse e-mail ou mot de passe incorrect." in response.content.decode()


@pytest.mark.django_db
def test_un_compte_desactive_ne_peut_pas_se_connecter(client, user):
    user.is_active = False
    user.save()

    response = connexion(client, user.email)

    assert response.context["user"].is_authenticated is False
