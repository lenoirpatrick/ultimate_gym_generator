from django import forms

from .models import MAX_ENTITIES, Connection, Entity


class ConnectionForm(forms.ModelForm):
    class Meta:
        model = Connection
        fields = ("base_url", "token")
        widgets = {
            "token": forms.PasswordInput(render_value=False, attrs={"autocomplete": "off"}),
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        has_token = bool(self.instance.pk and self.instance.token)
        self.fields["token"].required = not has_token
        self.fields["token"].help_text = (
            "Laisser vide pour conserver le jeton enregistré."
            if has_token
            else "Profil Home Assistant → Sécurité → Jetons d'accès longue durée. "
            "Chiffré avant enregistrement, jamais réaffiché."
        )

    def clean_token(self) -> str:
        """Un champ vide conserve le jeton existant plutôt que de l'effacer."""
        return self.cleaned_data.get("token") or self.instance.token


class EntityForm(forms.ModelForm):
    class Meta:
        model = Entity
        fields = ("entity_id", "label", "show_on_workout", "show_in_timer")
        widgets = {
            "entity_id": forms.TextInput(
                attrs={"placeholder": "switch.ventilateur", "autocapitalize": "none"}
            ),
            "label": forms.TextInput(attrs={"placeholder": "Ventilateur"}),
        }


class BaseEntityFormSet(forms.BaseModelFormSet):
    def add_fields(self, form, index) -> None:
        super().add_fields(form, index)
        if "DELETE" in form.fields:
            form.fields["DELETE"].label = "Ne plus suivre cette entité"


EntityFormSet = forms.modelformset_factory(
    Entity,
    form=EntityForm,
    formset=BaseEntityFormSet,
    extra=1,
    max_num=MAX_ENTITIES,
    validate_max=True,
    can_delete=True,
)
