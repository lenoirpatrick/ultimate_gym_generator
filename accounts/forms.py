from decimal import Decimal, InvalidOperation

from django import forms
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import User, UserEquipment

BODY_FIELDS = ("gender", "height_cm", "weight_kg")


def _format(weight) -> str:
    """Affiche une charge sans décimale inutile : 12 plutôt que 12.0."""
    return f"{float(weight):g}"


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


class EquipmentForm(forms.ModelForm):
    """Une ligne de matériel et les charges qu'il permet."""

    # Champ texte plutôt que le `JSONField` du modèle : personne ne devrait avoir
    # à écrire `[8, 12, 16]` à la main. La conversion se fait ici, et le champ
    # du modèle reçoit la liste déjà normalisée.
    weights = forms.CharField(
        label="Charges (kg)",
        required=False,
        help_text="Séparées par des virgules.",
        widget=forms.TextInput(attrs={"placeholder": "8, 12, 16, 24", "inputmode": "decimal"}),
    )

    class Meta:
        model = UserEquipment
        fields = ("equipment", "mode", "weights", "min_kg", "max_kg", "step_kg")
        # Rendu en `.ugg-segmented` (trois choix fermés) plutôt qu'en `<select>` : le
        # gabarit peut alors ne révéler que les champs du mode coché, en CSS pur, sur
        # le même patron que `.ugg-format__tune` (issue #37).
        widgets = {"mode": forms.RadioSelect}

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["step_kg"].help_text = "Écart entre deux crans, en kilogrammes."

        # `weights` est à la fois un champ du modèle (une liste JSON) et un champ de
        # formulaire déclaré ci-dessus (un texte) : `ModelForm.__init__` peuple
        # `self.initial["weights"]` avec la liste brute avant que ce constructeur ne
        # s'exécute. Sans réécriture systématique, une liste vide (mode réglable ou
        # sans charge — la grande majorité des lignes) laissait passer `[]` telle
        # quelle, que le widget affichait comme le texte littéral « [] » ; resoumettre
        # la ligne sans y toucher échouait alors avec « "[]" n'est pas un poids »,
        # empêchant tout réenregistrement d'une ligne existante. Toujours recalculer,
        # y compris pour une liste vide.
        self.initial["weights"] = ", ".join(_format(w) for w in self.instance.weights or [])

    def clean_weights(self) -> list[float]:
        """Accepte « 8, 12, 16 » — et refuse ce qui n'est pas un poids."""
        raw = self.cleaned_data.get("weights") or ""

        weights = set()
        for chunk in raw.replace(";", ",").split(","):
            chunk = chunk.strip().replace(",", ".")
            if not chunk:
                continue
            try:
                weight = Decimal(chunk)
            except InvalidOperation as exc:
                raise forms.ValidationError(f"« {chunk} » n'est pas un poids.") from exc
            if weight <= 0:
                raise forms.ValidationError("Une charge doit être supérieure à zéro.")
            # Stocké en nombre JSON : `Decimal` n'est pas sérialisable, et la
            # précision d'une charge de musculation ne l'exige pas.
            weights.add(float(weight))

        return sorted(weights)

    def clean(self) -> dict:
        """Chaque mode a ses champs obligatoires : les exiger ici évite une ligne inutilisable."""
        cleaned = super().clean()
        mode = cleaned.get("mode")

        if mode == UserEquipment.Mode.FIXED and not cleaned.get("weights"):
            self.add_error("weights", "Indique au moins une charge, ou choisis « Sans charge ».")

        if mode == UserEquipment.Mode.ADJUSTABLE:
            minimum, maximum, step = (cleaned.get(k) for k in ("min_kg", "max_kg", "step_kg"))

            if minimum is None or maximum is None or step is None:
                self.add_error(
                    None, "Une charge réglable demande un minimum, un maximum et un pas."
                )
            else:
                if minimum >= maximum:
                    self.add_error("max_kg", "Le maximum doit dépasser le minimum.")
                if step <= 0:
                    self.add_error("step_kg", "L'incrément doit être supérieur à zéro.")

        return cleaned


EquipmentFormSet = forms.modelformset_factory(
    UserEquipment, form=EquipmentForm, extra=1, can_delete=True
)


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
