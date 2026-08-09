"""SSO OpenID Connect : câblage conditionnel et projection des claims.

Le parcours complet (redirection, échange de jeton, rappel) dépend d'un
fournisseur d'identité réel ; il se valide en configurant l'installation selon
la procédure de docs/INSTALL.md. Ce module couvre ce qui est vérifiable
hors ligne : l'application reste inerte tant que le SSO n'est pas activé, et le
backend remplit correctement le compte à partir des claims.
"""

import pytest
from django.urls import NoReverseMatch, reverse

from accounts.models import User
from accounts.oidc import GymOIDCAuthenticationBackend

CLAIMS = {
    "email": "alex@example.test",
    "given_name": "Alex",
    "family_name": "Martin",
    "preferred_username": "amartin",
}


# --------------------------------------------------------------------------- #
# Désactivé par défaut
# --------------------------------------------------------------------------- #


def test_le_sso_est_desactive_par_defaut(settings):
    assert settings.OIDC_ENABLED is False


def test_aucune_route_sso_n_est_exposee_quand_il_est_desactive():
    with pytest.raises(NoReverseMatch):
        reverse("oidc_authentication_init")


def test_le_backend_oidc_n_est_pas_dans_la_chaine_d_authentification(settings):
    assert settings.AUTHENTICATION_BACKENDS == ["django.contrib.auth.backends.ModelBackend"]


@pytest.mark.django_db
def test_la_page_de_connexion_ne_propose_pas_le_sso_quand_il_est_desactive(client):
    content = client.get(reverse("accounts:login")).content.decode()

    assert "Se connecter avec" not in content


@pytest.mark.django_db
def test_la_page_de_connexion_propose_le_sso_quand_il_est_active(client, settings):
    """Le gabarit s'appuie sur le processeur de contexte, pas sur les routes."""
    settings.OIDC_ENABLED = True
    settings.OIDC_PROVIDER_NAME = "Google"

    # Sans les routes de mozilla_django_oidc, le lien ne peut pas être résolu :
    # on vérifie donc le déclencheur, pas le rendu complet.
    from core.context_processors import site

    contexte = site(client.request().wsgi_request)

    assert contexte["sso_enabled"] is True
    assert contexte["sso_provider_name"] == "Google"


# --------------------------------------------------------------------------- #
# Projection des claims sur le compte
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_les_claims_remplissent_l_identite_du_compte():
    backend = GymOIDCAuthenticationBackend.__new__(GymOIDCAuthenticationBackend)
    account = User(username="", email=CLAIMS["email"])

    backend._apply_claims(account, CLAIMS)

    assert account.first_name == "Alex"
    assert account.last_name == "Martin"
    assert account.username == "amartin"


@pytest.mark.django_db
def test_le_nom_d_utilisateur_retombe_sur_la_partie_locale_de_l_e_mail():
    backend = GymOIDCAuthenticationBackend.__new__(GymOIDCAuthenticationBackend)
    account = User(username="", email="alex@example.test")

    backend._apply_claims(account, {"email": "alex@example.test"})

    assert account.username == "alex"


@pytest.mark.django_db
def test_une_reconnexion_sso_n_ecrase_pas_les_mesures_corporelles():
    """Les mesures appartiennent à l'utilisateur, pas au fournisseur d'identité."""
    backend = GymOIDCAuthenticationBackend.__new__(GymOIDCAuthenticationBackend)
    account = User.objects.create_user(
        username="amartin",
        email=CLAIMS["email"],
        height_cm=172,
        weight_kg="64.5",
        gender="F",
    )

    backend.update_user(account, CLAIMS)

    account.refresh_from_db()
    assert account.height_cm == 172
    assert account.gender == "F"
    assert account.first_name == "Alex"


@pytest.mark.django_db
def test_un_nom_d_utilisateur_existant_n_est_pas_ecrase():
    backend = GymOIDCAuthenticationBackend.__new__(GymOIDCAuthenticationBackend)
    account = User(username="deja-defini", email=CLAIMS["email"])

    backend._apply_claims(account, CLAIMS)

    assert account.username == "deja-defini"
