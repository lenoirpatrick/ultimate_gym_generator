from dataclasses import dataclass

from django import forms

from accounts.models import UserEquipment
from exercises import catalog
from exercises.models import Muscle

from . import generator
from .models import Workout

#: Parts de favoris proposées. Un curseur libre suggérerait une précision qui
#: n'existe pas : ce qui compte est « un peu », « la moitié », « surtout ».
FAVORITES_CHOICES = (
    (0, "Aucun"),
    (25, "Un quart"),
    (50, "La moitié"),
    (75, "Trois quarts"),
    (100, "Uniquement"),
)

#: Une phrase par format, affichée en bulle d'aide — atteignable au survol
#: comme au clavier (voir le partiel `partials/format_options.html`).
FORMAT_HINTS: dict[str, str] = {
    Workout.Format.HIIT: (
        "Beaucoup d'exercices différents enchaînés, peu de tours : la variété prime "
        "sur la répétition."
    ),
    Workout.Format.TABATA: (
        "Huit séries d'un seul exercice : un effort bref, un repos plus court."
    ),
    Workout.Format.CIRCUIT: (
        "Peu d'exercices répétés en plusieurs tours, tant que la durée le permet : "
        "l'endurance prime sur la variété."
    ),
    Workout.Format.PYRAMID: ("Répétitions décroissantes puis croissantes, un exercice à la fois."),
}


def _tuning_field_name(workout_format: str, kind: str) -> str:
    return f"{kind}_{workout_format}"


@dataclass(frozen=True)
class FormatOption:
    """Un format de travail à afficher, avec ses réglages éventuels."""

    radio: forms.BoundField
    label: str
    hint: str
    work_field: forms.BoundField | None
    rest_field: forms.BoundField
    #: Récupération entre tours/blocs, distincte du repos entre exercices
    #: ci-dessus (issue #44 suite) — toujours présente, même pour la pyramide.
    recovery_field: forms.BoundField
    #: Pic de répétitions — seule la pyramide en a un (issue #34).
    reps_field: forms.BoundField | None


@dataclass(frozen=True)
class MuscleRegion:
    """Cases du champ « muscles » rassemblées sous une région du corps."""

    label: str
    boxes: list

    @property
    def selected_count(self) -> int:
        return sum(1 for box in self.boxes if box.data["selected"])


class WorkoutForm(forms.Form):
    """Paramètres d'une séance à composer.

    Les temps d'effort et de repos sont réglables par format (issue #26), ainsi
    que le pic de répétitions de la pyramide (issue #34) : un champ facultatif
    par format et par grandeur, généré depuis `generator.FORMAT_PERIODS` plutôt
    que recopié à la main. `clean` ne retient que les réglages correspondant au
    format effectivement coché — régler un format qu'on ne choisit pas ne peut
    donc pas bloquer l'envoi.
    """

    name = forms.CharField(
        label="Nom",
        required=False,
        max_length=80,
        help_text="Facultatif : distingue cette séance dans l'historique.",
    )
    duration_minutes = forms.TypedChoiceField(
        label="Durée (minutes)",
        choices=Workout.Duration.choices,
        coerce=int,
        initial=Workout.Duration.THIRTY,
        widget=forms.RadioSelect,
    )
    workout_format = forms.ChoiceField(
        label="Type de travail",
        choices=Workout.Format.choices,
        initial=Workout.Format.CIRCUIT,
        widget=forms.RadioSelect,
    )
    muscles = forms.ModelMultipleChoiceField(
        label="Parties du corps",
        queryset=Muscle.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Aucune sélection : tout le corps.",
    )
    favorites_ratio = forms.TypedChoiceField(
        label="Part de favoris",
        choices=FAVORITES_CHOICES,
        coerce=int,
        initial=25,
        widget=forms.RadioSelect,
        help_text="Proportion d'exercices puisés dans tes favoris.",
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        # Un choix par matériel réellement configuré : coché par défaut, mais
        # indépendant de cette configuration — décocher ici ne la modifie pas,
        # ça ne fait qu'écarter ce matériel de cette séance (issue #32).
        configured = list(UserEquipment.objects.filter(user=user)) if user else []
        if configured:
            self.fields["equipment"] = forms.MultipleChoiceField(
                label="Matériel pris en compte",
                choices=[(item.equipment, item.get_equipment_display()) for item in configured],
                required=False,
                initial=[item.equipment for item in configured],
                widget=forms.CheckboxSelectMultiple,
            )

        for value, periods in generator.FORMAT_PERIODS.items():
            if periods.work is not None:
                self.fields[_tuning_field_name(value, "work")] = forms.IntegerField(
                    label="Effort (s)",
                    required=False,
                    initial=periods.work,
                    min_value=generator.MIN_WORK_SECONDS,
                    max_value=generator.MAX_WORK_SECONDS,
                )
            if periods.peak_reps is not None:
                self.fields[_tuning_field_name(value, "reps")] = forms.IntegerField(
                    label="Répétitions au pic",
                    required=False,
                    initial=periods.peak_reps,
                    min_value=generator.MIN_PYRAMID_PEAK,
                    max_value=generator.MAX_PYRAMID_PEAK,
                )
            self.fields[_tuning_field_name(value, "rest")] = forms.IntegerField(
                label="Repos (s)",
                required=False,
                initial=periods.rest,
                min_value=generator.MIN_REST_SECONDS,
                max_value=generator.MAX_REST_SECONDS,
            )
            self.fields[_tuning_field_name(value, "recovery")] = forms.IntegerField(
                label="Récupération entre tours (s)",
                required=False,
                initial=periods.recovery,
                min_value=generator.MIN_RECOVERY_SECONDS,
                max_value=generator.MAX_RECOVERY_SECONDS,
                help_text="Pause entre deux tours de circuit, ou entre deux blocs.",
            )

    def format_options(self) -> list[FormatOption]:
        """Un `FormatOption` par format, dans l'ordre d'affichage du formulaire."""
        radios = {radio.data["value"]: radio for radio in self["workout_format"]}

        options = []
        for value, label in Workout.Format.choices:
            work_key = _tuning_field_name(value, "work")
            reps_key = _tuning_field_name(value, "reps")
            options.append(
                FormatOption(
                    radio=radios[value],
                    label=label,
                    hint=FORMAT_HINTS.get(value, ""),
                    work_field=self[work_key] if work_key in self.fields else None,
                    rest_field=self[_tuning_field_name(value, "rest")],
                    recovery_field=self[_tuning_field_name(value, "recovery")],
                    reps_field=self[reps_key] if reps_key in self.fields else None,
                )
            )
        return options

    def muscle_regions(self) -> list[MuscleRegion]:
        """Cases du champ « muscles », groupées par région (issue #26).

        Le regroupement est un pur habillage d'affichage : le champ reste un
        `ModelMultipleChoiceField` unique, aucune valeur ne change de sens.
        """
        # `box.data["value"]` est un `ModelChoiceIteratorValue` : sa comparaison
        # et son hachage délèguent à la valeur brute (le pk), pas à sa
        # représentation textuelle — l'indexer par `str(m.pk)` échouerait.
        boxes = {box.data["value"]: box for box in self["muscles"]}
        grouped = catalog.group_by_region(self.fields["muscles"].queryset)
        return [
            MuscleRegion(label=region, boxes=[boxes[m.pk] for m in muscles])
            for region, muscles in grouped.items()
        ]

    def clean(self):
        cleaned = super().clean()
        chosen = cleaned.get("workout_format")

        # Seuls les réglages du format choisi comptent : une valeur hors bornes
        # laissée dans un format qu'on n'a pas retenu ne doit ni apparaître
        # dans le résultat, ni faire échouer l'envoi.
        active = set()
        if chosen:
            work_key = _tuning_field_name(chosen, "work")
            if work_key in self.fields:
                active.add(work_key)
            reps_key = _tuning_field_name(chosen, "reps")
            if reps_key in self.fields:
                active.add(reps_key)
            active.add(_tuning_field_name(chosen, "rest"))
            active.add(_tuning_field_name(chosen, "recovery"))

        for name in list(self.fields):
            if name.startswith(("work_", "rest_", "reps_", "recovery_")) and name not in active:
                self._errors.pop(name, None)
                cleaned.pop(name, None)

        cleaned["work_seconds"] = (
            cleaned.get(_tuning_field_name(chosen, "work")) if chosen else None
        )
        cleaned["rest_seconds"] = (
            cleaned.get(_tuning_field_name(chosen, "rest")) if chosen else None
        )
        cleaned["recovery_seconds"] = (
            cleaned.get(_tuning_field_name(chosen, "recovery")) if chosen else None
        )
        cleaned["peak_reps"] = cleaned.get(_tuning_field_name(chosen, "reps")) if chosen else None
        return cleaned
