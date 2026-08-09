from django import forms

from exercises.models import Muscle

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


class WorkoutForm(forms.Form):
    """Paramètres d'une séance à composer."""

    duration_minutes = forms.TypedChoiceField(
        label="Durée",
        choices=Workout.Duration.choices,
        coerce=int,
        initial=Workout.Duration.STANDARD,
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
        help_text="Proportion d'exercices puisés dans tes favoris.",
    )
