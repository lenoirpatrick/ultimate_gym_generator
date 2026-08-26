from datetime import timedelta

import pytest
from django.utils import timezone

from health.models import Activity, DailySteps, WeightMeasurement

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
    assert 'aria-live="polite"' in content


def test_le_filtrage_par_type_restreint_les_activites_affichees(logged_client, user):
    now = timezone.now()
    Activity.objects.create(
        user=user,
        activity_type=Activity.ActivityType.RUNNING,
        started_at=now,
        ended_at=now + timedelta(minutes=30),
    )
    Activity.objects.create(
        user=user,
        activity_type=Activity.ActivityType.CYCLING,
        started_at=now,
        ended_at=now + timedelta(hours=1),
    )

    # Requête HTMX : seul le fragment de résultats revient, sans le
    # formulaire de filtre (qui, lui, liste toujours tous les types en
    # option — comparer sur la page entière serait un faux négatif).
    response = logged_client.get("/sante/", {"type": "running"}, HTTP_HX_REQUEST="true")
    content = response.content.decode()

    assert "Course à pied" in content
    assert "Vélo" not in content


def test_le_filtrage_par_periode_exclut_les_activites_hors_plage(logged_client, user):
    now = timezone.now()
    Activity.objects.create(
        user=user,
        activity_type=Activity.ActivityType.RUNNING,
        started_at=now - timedelta(days=100),
        ended_at=now - timedelta(days=100) + timedelta(minutes=30),
    )

    response = logged_client.get("/sante/", {"periode": "7"})
    assert "Aucune activité sur cette période" in response.content.decode()

    response = logged_client.get("/sante/", {"periode": "tout"})
    assert "Aucune activité sur cette période" not in response.content.decode()


def test_une_requete_htmx_ne_rend_que_le_fragment(logged_client, user):
    response = logged_client.get("/sante/", HTTP_HX_REQUEST="true")
    assert response.status_code == 200
    assert b"<html" not in response.content


def test_le_kpi_de_pas_moyens_apparait_avec_des_totaux_importes(logged_client, user):
    today = timezone.now().date()
    DailySteps.objects.create(user=user, date=today, steps=8000)
    DailySteps.objects.create(user=user, date=today - timedelta(days=1), steps=12000)

    response = logged_client.get("/sante/")
    content = response.content.decode()

    assert "Pas moyens (jour)" in content
    assert "10 000" in content


def test_le_filtrage_par_periode_exclut_les_pas_hors_plage(logged_client, user):
    today = timezone.now().date()
    DailySteps.objects.create(user=user, date=today - timedelta(days=100), steps=9000)

    response = logged_client.get("/sante/", {"periode": "7"})
    assert "aucun total importé" in response.content.decode()

    response = logged_client.get("/sante/", {"periode": "tout"})
    assert "aucun total importé" not in response.content.decode()
