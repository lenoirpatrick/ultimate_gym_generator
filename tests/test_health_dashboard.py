from datetime import timedelta

import pytest
from django.utils import timezone

from health.models import Activity, WeightMeasurement

pytestmark = pytest.mark.django_db


def test_sans_donnee_la_page_propose_d_importer(logged_client):
    response = logged_client.get("/sante/")
    assert response.status_code == 200
    assert "Aucune donnée importée" in response.content.decode()


def test_avec_des_donnees_les_kpi_et_graphiques_apparaissent(logged_client, user):
    now = timezone.now()
    WeightMeasurement.objects.create(user=user, recorded_at=now, weight_kg="80.0")
    Activity.objects.create(
        user=user,
        activity_type=Activity.ActivityType.RUNNING,
        started_at=now - timedelta(hours=1),
        ended_at=now - timedelta(minutes=30),
        distance_meters=5000,
    )

    response = logged_client.get("/sante/")
    content = response.content.decode()

    assert response.status_code == 200
    assert "health-chart-data" in content
    assert "Poids actuel" in content
    assert "80.00 kg" in content


def test_une_activite_hors_des_trente_derniers_jours_n_apparait_pas(logged_client, user):
    now = timezone.now()
    WeightMeasurement.objects.create(user=user, recorded_at=now, weight_kg="80.0")
    Activity.objects.create(
        user=user,
        activity_type=Activity.ActivityType.RUNNING,
        started_at=now - timedelta(days=100),
        ended_at=now - timedelta(days=100) + timedelta(minutes=30),
    )

    response = logged_client.get("/sante/")
    assert "Aucune activité sur les 30 derniers jours" in response.content.decode()
