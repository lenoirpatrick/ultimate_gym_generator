from django.db import models

from .fields import EncryptedTextField
from .registry import PROVIDER_CHOICES, get_spec


class ProviderCredential(models.Model):
    """Identifiants d'accès à un fournisseur d'IA générative.

    Une entrée par fournisseur : la page de configuration présente la liste du
    registre et complète chaque ligne avec sa configuration, si elle existe.
    """

    provider = models.CharField("fournisseur", max_length=32, choices=PROVIDER_CHOICES, unique=True)
    secret = EncryptedTextField("clé d'API", blank=True)
    base_url = models.URLField("URL de base", max_length=200, blank=True)
    default_model = models.CharField("modèle par défaut", max_length=100, blank=True)
    is_active = models.BooleanField("actif", default=True)
    created_at = models.DateTimeField("créé le", auto_now_add=True)
    updated_at = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        verbose_name = "credential IA"
        verbose_name_plural = "credentials IA"
        ordering = ("provider",)

    def __str__(self) -> str:
        return self.spec.name

    @property
    def spec(self):
        return get_spec(self.provider)

    @property
    def masked_secret(self) -> str:
        """Représentation affichable du secret — jamais la valeur complète."""
        if not self.secret:
            return ""
        tail = self.secret[-4:]
        return f"{'•' * 8}{tail}"

    @property
    def effective_base_url(self) -> str:
        return self.base_url or self.spec.default_base_url

    @property
    def effective_model(self) -> str:
        return self.default_model or self.spec.default_model

    @property
    def is_configured(self) -> bool:
        """Vrai lorsque le fournisseur dispose du minimum pour être appelé."""
        if self.spec.requires_api_key:
            return bool(self.secret)
        return bool(self.effective_base_url)
