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
        if spec.requires_api_key:
            secret.help_text = (
                "Laisser vide pour conserver la clé enregistrée."
                if self.instance.pk and self.instance.secret
                else "La clé est chiffrée avant enregistrement et n'est jamais réaffichée."
            )
        else:
            secret.required = False
            secret.widget = forms.HiddenInput()

        self.fields["base_url"].help_text = spec.base_url_help or (
            f"Laisser vide pour utiliser {spec.default_base_url}."
            if spec.default_base_url
            else "Laisser vide pour l'URL officielle du fournisseur."
        )
        # Quand le fournisseur sait publier son catalogue, ce champ est remplacé
        # par un menu déroulant dès qu'une clé est enregistrée — l'aide annonce
        # donc ce qui attend l'utilisateur au prochain passage.
        if spec.supports_model_listing and not (self.instance.pk and self.instance.is_configured):
            self.fields["default_model"].help_text = (
                f"Laisser vide pour utiliser {spec.default_model}. "
                "Une fois la clé enregistrée, le modèle se choisira dans la liste "
                "des modèles disponibles sur ton compte."
            )
        else:
            self.fields["default_model"].help_text = (
                f"Laisser vide pour utiliser {spec.default_model}. "
                "L'identifiant doit correspondre au catalogue actuel du fournisseur."
            )

    def clean_secret(self) -> str:
        """Un champ vide conserve la clé existante plutôt que de l'effacer."""
        value = self.cleaned_data.get("secret", "")
        if not value and self.instance.pk:
            return self.instance.secret
        if not value and self.spec.requires_api_key:
            raise forms.ValidationError("Ce fournisseur nécessite une clé d'API.")
        return value
