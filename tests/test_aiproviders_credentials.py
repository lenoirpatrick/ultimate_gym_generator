"""Credentials IA : chiffrement au repos et non-divulgation du secret."""

import importlib

import pytest
from django.db import connection

from aiproviders.models import ProviderCredential

SECRET = "cle-secrete-de-test-f3a9"


@pytest.mark.django_db
def test_le_secret_fait_un_aller_retour_complet():
    ProviderCredential.objects.create(provider="gemini", secret=SECRET)

    assert ProviderCredential.objects.get(provider="gemini").secret == SECRET


@pytest.mark.django_db
def test_le_secret_est_chiffre_en_base():
    credential = ProviderCredential.objects.create(provider="claude_gateway", secret=SECRET)

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT secret FROM aiproviders_providercredential WHERE id = %s", [credential.pk]
        )
        stored = cursor.fetchone()[0]

    assert stored != SECRET
    assert SECRET not in stored


@pytest.mark.django_db
def test_le_secret_est_masque_a_l_affichage():
    credential = ProviderCredential.objects.create(provider="gemini", secret=SECRET)

    masked = credential.masked_secret

    assert masked.endswith("f3a9")
    assert SECRET not in masked


@pytest.mark.django_db
def test_les_valeurs_par_defaut_du_registre_comblent_les_champs_vides():
    credential = ProviderCredential.objects.create(provider="gemini", secret=SECRET)

    assert credential.effective_model == "gemini-2.5-pro"
    assert credential.effective_base_url == "https://generativelanguage.googleapis.com"


@pytest.mark.django_db
def test_gemini_n_est_pas_configure_sans_cle_d_api():
    assert ProviderCredential.objects.create(provider="gemini").is_configured is False


@pytest.mark.django_db
def test_la_migration_supprime_les_credentials_des_fournisseurs_retires():
    """Issue #151 : un credential orphelin ferait lever `KeyError` à `get_spec()`."""
    from django.apps import apps

    migration = importlib.import_module("aiproviders.migrations.0003_remove_legacy_providers")
    for provider in migration.REMOVED_PROVIDERS:
        ProviderCredential.objects.create(provider=provider, secret=SECRET)
    ProviderCredential.objects.create(provider="gemini", secret=SECRET)

    migration.delete_removed_credentials(apps, None)

    assert list(ProviderCredential.objects.values_list("provider", flat=True)) == ["gemini"]
