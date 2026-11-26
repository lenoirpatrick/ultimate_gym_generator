from django import forms

from .models import ProviderCredential
from .registry import ProviderSpec


class ProviderCredentialForm(forms.ModelForm):
    class Meta:
        model = ProviderCredential
        fields = ("secret", "base_url", "default_model", "is_active")
        widgets = {
            "secret": forms.PasswordInput(render_value=False, attrs={"autocomplete": "off"}),
        }

    def __init__(self, *args, spec: ProviderSpec, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.spec = spec

        secret = self.fields["secret"]
        secret.label = spec.credential_field_label
        secret.help_text = (
            "Laisser vide pour conserver la valeur enregistrée."
            if self.instance.pk and self.instance.secret
            else "La valeur est chiffrée avant enregistrement et n'est jamais réaffichée."
        )

        base_url = self.fields["base_url"]
        base_url.required = spec.requires_base_url
        base_url.help_text = spec.base_url_help or (
            f"Laisser vide pour utiliser {spec.default_base_url}."
            if spec.default_base_url
            else "Laisser vide pour l'URL officielle du fournisseur."
        )
        #: Catalogue distant chargé en HTMX : il suppose des credentials
        #: utilisables, donc une configuration déjà enregistrée.
        self.offers_model_picker = bool(
            spec.supports_model_listing and self.instance.pk and self.instance.is_configured
        )

        if spec.fixed_models and not self.offers_model_picker:
            self.fields["default_model"] = self._fixed_model_field(spec)
        # Quand le fournisseur sait publier son catalogue, ce champ est remplacé
        # par un menu déroulant dès qu'une clé est enregistrée — l'aide annonce
        # donc ce qui attend l'utilisateur au prochain passage.
        elif spec.supports_model_listing and not (self.instance.pk and self.instance.is_configured):
            self.fields["default_model"].help_text = (
                f"Laisser vide pour utiliser {spec.default_model}. "
                "Une fois la configuration enregistrée, le modèle se choisira dans "
                "la liste des modèles disponibles."
            )
        else:
            self.fields["default_model"].help_text = (
                f"Laisser vide pour utiliser {spec.default_model}. "
                "L'identifiant doit correspondre au catalogue actuel du fournisseur."
            )

    @staticmethod
    def _fixed_model_field(spec: ProviderSpec) -> forms.ChoiceField:
        """Menu déroulant d'un catalogue fermé, « Par défaut » en tête.

        Le choix vide est conservé tel quel en base : il suit le modèle par
        défaut du registre si celui-ci change un jour.
        """
        return forms.ChoiceField(
            label="Modèle par défaut",
            choices=[("", f"Par défaut ({spec.default_model})"), *spec.fixed_models],
            required=False,
            help_text=f"« Par défaut » utilise {spec.default_model}."
            + (
                " Une fois la configuration enregistrée, la liste sera lue sur le fournisseur."
                if spec.supports_model_listing
                else ""
            ),
        )

    def clean_secret(self) -> str:
        """Un champ vide conserve la clé existante plutôt que de l'effacer."""
        value = self.cleaned_data.get("secret", "")
        if not value and self.instance.pk:
            return self.instance.secret
        if not value:
            raise forms.ValidationError(
                f"Ce fournisseur nécessite un secret : {self.spec.credential_field_label.lower()}."
            )
        return value
