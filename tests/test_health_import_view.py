from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from health.models import Activity, DailySteps, WeightMeasurement

pytestmark = pytest.mark.django_db

FIXTURE = Path(__file__).parent / "fixtures" / "health_export.xml"


def test_l_ecran_d_import_s_affiche(logged_client):
    response = logged_client.get("/sante/import/")
    assert response.status_code == 200
    assert "export.xml" in response.content.decode()


def test_importer_un_fichier_valide_met_a_jour_les_compteurs(logged_client, user):
    upload = SimpleUploadedFile("export.xml", FIXTURE.read_bytes(), content_type="text/xml")
    response = logged_client.post("/sante/import/", {"file": upload})

    assert response.status_code == 200
    assert "Import terminé" in response.content.decode()
    assert WeightMeasurement.objects.filter(user=user).count() == 2
    assert Activity.objects.filter(user=user).count() == 2
    assert DailySteps.objects.filter(user=user).count() == 2


def test_une_extension_incorrecte_est_rejetee(logged_client):
    upload = SimpleUploadedFile("export.zip", b"peu importe", content_type="application/zip")
    response = logged_client.post("/sante/import/", {"file": upload})

    assert response.status_code == 200
    assert "extension .xml" in response.content.decode()


@override_settings(APPLE_HEALTH_IMPORT_MAX_BYTES=10)
def test_un_fichier_trop_volumineux_est_rejete(logged_client):
    upload = SimpleUploadedFile("export.xml", FIXTURE.read_bytes(), content_type="text/xml")
    response = logged_client.post("/sante/import/", {"file": upload})

    assert response.status_code == 200
    assert "taille maximale" in response.content.decode()


def test_since_borne_l_import_et_l_affiche(logged_client, user):
    upload = SimpleUploadedFile("export.xml", FIXTURE.read_bytes(), content_type="text/xml")
    response = logged_client.post("/sante/import/", {"file": upload, "since": "2024-01-05"})
    content = response.content.decode()

    assert response.status_code == 200
    assert "antérieur" in content
    assert WeightMeasurement.objects.filter(user=user).count() == 1
    assert Activity.objects.filter(user=user).count() == 0
