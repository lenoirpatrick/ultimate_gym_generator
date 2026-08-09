from django import forms
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import User

BODY_FIELDS = ("gender", "height_cm", "weight_kg")

IDENTITY_FIELDS = ("email", "first_name", "last_name")


class EmailAuthenticationForm(AuthenticationForm):
    """Connexion par adresse e-mail.

    Le champ garde le nom `username` imposé par Django ; seul l'habillage change.
    """

    error_messages = {
        # Un message unique pour l'e-mail inconnu et le mot de passe faux : le
        # distinguer révélerait quels comptes existent sur l'installation.
        "invalid_login": "Adresse e-mail ou mot de passe incorrect.",
        "inactive": "Ce compte est désactivé.",
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Adresse e-mail"
        # Un e-mail se saisit souvent d'une main sur un téléphone, à la salle :
        # le clavier doit proposer « @ » et la saisie automatique doit s'appliquer.
        self.fields["username"].widget = forms.EmailInput(
            attrs={"autocomplete": "email", "autofocus": True, "inputmode": "email"}
        )

    def clean_username(self) -> str:
        """Normalise comme `User.save()`, pour qu'une majuscule ne bloque pas la connexion."""
        return self.cleaned_data["username"].strip().lower()


class AvatarFieldMixin(forms.ModelForm):
    """Refuse un avatar trop lourd avant qu'il n'atteigne le disque."""

    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        limit = settings.MAX_AVATAR_BYTES

        if avatar and getattr(avatar, "size", 0) > limit:
            raise forms.ValidationError(
                f"Image trop lourde ({avatar.size // 1024} Ko). "
                f"Maximum autorisé : {limit // 1024} Ko."
            )
        return avatar


class FirstRunForm(UserCreationForm):
    """Création du tout premier compte, qui reçoit les droits d'administration."""

    class Meta:
        model = User
        fields = IDENTITY_FIELDS

    def save(self, commit: bool = True) -> User:
        user = super().save(commit=False)
        # Le premier compte administre l'installation : sans lui, personne ne
        # pourrait créer les suivants ni accéder à l'administration.
        user.is_staff = True
        user.is_superuser = True
        if commit:
            user.save()
        return user


class SelfRegistrationForm(UserCreationForm):
    """Inscription libre, disponible seulement si `ALLOW_SELF_REGISTRATION`."""

    class Meta:
        model = User
        fields = IDENTITY_FIELDS


class ProfileForm(AvatarFieldMixin):
    """Édition par l'utilisateur de son propre compte."""

    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "avatar", *BODY_FIELDS)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["height_cm"].help_text = "En centimètres, entre 90 et 260."
        self.fields["weight_kg"].help_text = "En kilogrammes, avec une décimale."
        self.fields[
            "avatar"
        ].help_text = f"Image carrée de préférence. {settings.MAX_AVATAR_BYTES // 1024} Ko maximum."


class StaffUserCreationForm(UserCreationForm):
    """Création d'un compte par un membre du personnel."""

    class Meta:
        model = User
        fields = (*IDENTITY_FIELDS, "is_staff")


class StaffUserChangeForm(AvatarFieldMixin):
    """Modification d'un compte par un membre du personnel.

    Le mot de passe n'y figure pas : il se change depuis le profil de son
    titulaire, ou se réinitialise depuis l'administration Django.
    """

    class Meta:
        model = User
        fields = (
            *IDENTITY_FIELDS,
            "avatar",
            *BODY_FIELDS,
            "is_active",
            "is_staff",
        )

    def __init__(self, *args, editing_self: bool = False, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.editing_self = editing_self

        if editing_self:
            # Se retirer ses propres droits ou se désactiver soi-même laisserait
            # potentiellement l'installation sans administrateur.
            for field in ("is_active", "is_staff"):
                self.fields[field].disabled = True
                self.fields[field].help_text = "Non modifiable sur son propre compte."

    def clean_is_staff(self):
        if self.editing_self:
            return self.instance.is_staff
        return self.cleaned_data["is_staff"]

    def clean_is_active(self):
        if self.editing_self:
            return self.instance.is_active
        return self.cleaned_data["is_active"]
