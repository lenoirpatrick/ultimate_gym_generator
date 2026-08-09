"""Registre des fournisseurs : cohérence des fiches et liens exposés."""

import pytest
from django.urls import reverse

from aiproviders.registry import PROVIDERS, get_spec


@pytest.mark.parametrize("spec", PROVIDERS, ids=lambda spec: spec.slug)
def test_chaque_fournisseur_expose_ses_liens(spec):
    assert spec.credential_url.startswith("https://")
    assert spec.docs_url.startswith("https://")
    assert spec.credential_label


def test_les_slugs_sont_uniques():
    slugs = [spec.slug for spec in PROVIDERS]

    assert len(slugs) == len(set(slugs))


def test_un_slug_inconnu_leve_une_erreur():
    with pytest.raises(KeyError):
        get_spec("inexistant")


@pytest.mark.django_db
def test_la_liste_affiche_le_lien_de_creation_de_cle(staff_client):
    content = staff_client.get(reverse("aiproviders:list")).content.decode()

    for spec in PROVIDERS:
        assert spec.credential_url in content


@pytest.mark.django_db
def test_le_formulaire_affiche_le_lien_de_creation_de_cle(staff_client):
    content = staff_client.get(reverse("aiproviders:edit", args=["anthropic"])).content.decode()

    assert "https://console.anthropic.com/settings/keys" in content
