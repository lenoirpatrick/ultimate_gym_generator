from django.contrib import admin

from .models import ProviderCredential


@admin.register(ProviderCredential)
class ProviderCredentialAdmin(admin.ModelAdmin):
    list_display = ("provider", "masked_secret", "default_model", "is_active", "updated_at")
    list_filter = ("is_active", "provider")
    # Le secret n'est pas éditable depuis l'admin : la page /settings/ai/ est le
    # seul point d'entrée, avec son masquage et son test de connexion.
    exclude = ("secret",)
    readonly_fields = ("masked_secret", "created_at", "updated_at")
