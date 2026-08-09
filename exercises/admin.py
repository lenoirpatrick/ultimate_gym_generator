from django.contrib import admin

from .models import Exercise, Muscle


@admin.register(Muscle)
class MuscleAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "slug")


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    """Consultation du catalogue.

    Les fiches proviennent du fichier livré avec l'application : les modifier
    ici serait perdu au prochain import.
    """

    list_display = ("name", "category", "level", "equipment", "mechanic")
    list_filter = ("category", "level", "equipment", "mechanic", "force")
    search_fields = ("name", "slug")
    filter_horizontal = ("primary_muscles", "secondary_muscles")
