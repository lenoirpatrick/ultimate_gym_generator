from django.contrib import admin

from .models import Entity


@admin.register(Entity)
class EntityAdmin(admin.ModelAdmin):
    """Consultation seulement utile au dépannage : le jeton, lui, n'y figure pas."""

    list_display = ("label", "entity_id", "show_on_workout", "show_in_timer")
