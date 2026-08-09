"""Adaptation du backend OpenID Connect au modèle utilisateur de l'application.

Chargé uniquement lorsque `OIDC_ENABLED` est vrai — voir `config.settings.base`.
"""

from mozilla_django_oidc.auth import OIDCAuthenticationBackend


class GymOIDCAuthenticationBackend(OIDCAuthenticationBackend):
    """Renseigne les champs du compte à partir des claims du fournisseur.

    Les mesures corporelles (sexe, taille, poids) ne proviennent jamais du
    fournisseur d'identité : elles restent saisies par l'utilisateur depuis son
    profil, et une reconnexion SSO ne les écrase pas.
    """

    def create_user(self, claims: dict):
        # `super()` créerait le compte avec un nom d'utilisateur en premier
        # argument, que le modèle n'a plus : l'e-mail est le seul identifiant.
        user = self.UserModel.objects.create_user(email=claims.get("email"))
        self._apply_claims(user, claims)
        user.save()
        return user

    def update_user(self, user, claims: dict):
        self._apply_claims(user, claims)
        user.save()
        return user

    @staticmethod
    def _apply_claims(user, claims: dict) -> None:
        user.first_name = claims.get("given_name") or user.first_name
        user.last_name = claims.get("family_name") or user.last_name
