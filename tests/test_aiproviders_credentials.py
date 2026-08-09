"""Credentials IA : chiffrement au repos et non-divulgation du secret."""

import pytest
from django.db import connection

from aiproviders.models import ProviderCredential

SECRET = "sk-ant-secret-de-test-f3a9"


@pytest.mark.django_db
def test_le_secret_fait_un_aller_retour_complet():
    ProviderCredential.objects.create(provider="anthropic", secret=SECRET)

    assert ProviderCredential.objects.get(provider="anthropic").secret == SECRET


@pytest.mark.django_db
def test_le_secret_est_chiffre_en_base():
    credential = ProviderCredential.objects.create(provider="mistral", secret=SECRET)

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
    credential = ProviderCredential.objects.create(provider="ollama")

    assert credential.effective_model == "llama3.1"
    assert credential.effective_base_url == "http://localhost:11434"


@pytest.mark.django_db
def test_ollama_est_considere_configure_sans_cle_d_api():
    assert ProviderCredential.objects.create(provider="ollama").is_configured is True


@pytest.mark.django_db
def test_anthropic_n_est_pas_configure_sans_cle_d_api():
    assert ProviderCredential.objects.create(provider="anthropic").is_configured is False
