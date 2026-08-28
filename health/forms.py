from django import forms
from django.conf import settings

from .models import Activity


class HealthImportForm(forms.Form):
    file = forms.FileField(label="Export Apple Health (export.xml)")
    #: Borne l'import à partir de cette date (issue #74) — laisser vide pour
    #: tout importer. Un seul champ couvre les deux cas demandés (date précise
    #: ou année entière) : sélectionner le 1er janvier d'une année revient à
    #: choisir cette année, sans dupliquer le champ.
    since = forms.DateField(
        label="Importer depuis (optionnel)",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Laisser vide pour tout importer. Pour une année entière, "
        "choisir le 1er janvier de cette année.",
    )

    def clean_file(self):
        uploaded = self.cleaned_data["file"]

        if not uploaded.name.lower().endswith(".xml"):
            raise forms.ValidationError(
                "Le fichier doit être l'export XML d'Apple Health (extension .xml)."
            )

        if uploaded.size > settings.APPLE_HEALTH_IMPORT_MAX_BYTES:
            max_mb = settings.APPLE_HEALTH_IMPORT_MAX_BYTES // (1024 * 1024)
            raise forms.ValidationError(
                f"Le fichier dépasse la taille maximale acceptée ({max_mb} Mo)."
            )

        return uploaded


class ApiKeyForm(forms.Form):
    label = forms.CharField(
        label="Nom de la clé",
        max_length=120,
        widget=forms.TextInput(attrs={"placeholder": "ex. iPhone — Raccourci"}),
    )


class ActivityTypeForm(forms.Form):
    """Modification du type d'une activité (issue #81).

    Un `<select>`, pas un contrôle segmenté : dix valeurs closes, la règle du
    projet réserve le segmenté aux choix fermés à peu de valeurs (voir le
    matériel de l'utilisateur, même patron).
    """

    activity_type = forms.ChoiceField(
        label="Type d'activité", choices=Activity.ActivityType.choices
    )
