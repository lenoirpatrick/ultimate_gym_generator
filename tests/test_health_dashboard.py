from datetime import timedelta

import pytest
from django.utils import timezone

from exercises.models import Exercise
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

    # Comparaison sur le titre de chaque carte (`<p>...</p>`), pas sur le nom
    # brut du type : le sélecteur d'édition de type de chaque carte restante
    # liste, lui, toujours tous les types en option (issue #81).
    response = logged_client.get("/sante/", {"type": "running"}, HTTP_HX_REQUEST="true")
    content = response.content.decode()

    assert ">Course à pied</p>" in content
    assert ">Vélo</p>" not in content


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


def test_les_calories_apparaissent_sur_la_carte_et_en_kpi(logged_client, user):
    now = timezone.now()
    Activity.objects.create(
        user=user,
        activity_type=Activity.ActivityType.RUNNING,
        started_at=now,
        ended_at=now + timedelta(minutes=30),
        active_energy_kcal=320,
    )

    response = logged_client.get("/sante/")
    content = response.content.decode()

    assert "320 kcal" in content
    assert "Calories actives" in content


def test_un_graphique_sans_serie_ne_s_affiche_pas(logged_client, user):
    # Seuls les pas ont une donnée sur la période : poids, volume et allure
    # ne doivent montrer aucune carte (issue #84).
    DailySteps.objects.create(user=user, date=timezone.now().date(), steps=8000)

    response = logged_client.get("/sante/")
    content = response.content.decode()

    assert "Pas par jour" in content
    assert "Poids</p>" not in content
    assert "Volume d'activité" not in content
    assert "Allure de course" not in content


def test_la_recherche_restreint_les_activites_affichees(logged_client, user):
    now = timezone.now()
    Activity.objects.create(
        user=user,
        activity_type=Activity.ActivityType.RUNNING,
        started_at=now,
        ended_at=now + timedelta(minutes=30),
        source="Montre Garmin",
    )
    Activity.objects.create(
        user=user,
        activity_type=Activity.ActivityType.CYCLING,
        started_at=now,
        ended_at=now + timedelta(hours=1),
        source="iPhone",
    )

    response = logged_client.get("/sante/", {"q": "garmin"}, HTTP_HX_REQUEST="true")
    content = response.content.decode()

    assert ">Course à pied</p>" in content
    assert ">Vélo</p>" not in content


def test_le_rappel_d_exercice_lie_apparait_pour_un_type_reconnu(logged_client, user):
    Exercise.objects.create(
        slug="Running_Treadmill", name="Running, Treadmill", category="cardio", level="beginner"
    )
    now = timezone.now()
    Activity.objects.create(
        user=user,
        activity_type=Activity.ActivityType.RUNNING,
        started_at=now,
        ended_at=now + timedelta(minutes=30),
    )

    response = logged_client.get("/sante/")
    content = response.content.decode()

    assert "Running, Treadmill" in content


def test_aucun_rappel_d_exercice_pour_un_type_sans_equivalent(logged_client, user):
    now = timezone.now()
    Activity.objects.create(
        user=user,
        activity_type=Activity.ActivityType.STRENGTH_TRAINING,
        started_at=now,
        ended_at=now + timedelta(minutes=30),
    )

    response = logged_client.get("/sante/")

    assert "ugg-disclosure" not in response.content.decode()


def test_deux_activites_du_meme_type_ont_des_rappels_aux_id_distincts(logged_client, user):
    # Issue #82 : sans id distinct par activité, les deux rappels
    # partageraient le même id — la vignette photo agrandirait alors les
    # deux à la fois (:target matche tout élément portant l'id ciblé).
    Exercise.objects.create(slug="Bicycling", name="Bicycling", category="cardio", level="beginner")
    now = timezone.now()
    first = Activity.objects.create(
        user=user,
        activity_type=Activity.ActivityType.CYCLING,
        started_at=now,
        ended_at=now + timedelta(minutes=30),
    )
    second = Activity.objects.create(
        user=user,
        activity_type=Activity.ActivityType.CYCLING,
        started_at=now - timedelta(hours=1),
        ended_at=now - timedelta(hours=1) + timedelta(minutes=30),
    )

    content = logged_client.get("/sante/").content.decode()

    assert f'id="exercise-{first.pk}-description"' in content
    assert f'id="exercise-{second.pk}-description"' in content


def test_un_graphique_avec_serie_propose_de_l_agrandir(logged_client, user):
    WeightMeasurement.objects.create(user=user, recorded_at=timezone.now(), weight_kg="80.0")

    response = logged_client.get("/sante/")
    content = response.content.decode()

    assert 'href="#graphique-weight"' in content
    assert 'id="graphique-weight"' in content
    assert 'id="chart-weight-large"' in content
    assert "Réinitialiser le zoom" in content


def test_un_graphique_sans_serie_n_a_pas_de_lightbox(logged_client, user):
    # Seuls les pas ont une donnée : pas de lightbox pour poids/volume/allure,
    # cohérent avec l'absence de leur carte (issue #84).
    DailySteps.objects.create(user=user, date=timezone.now().date(), steps=8000)

    response = logged_client.get("/sante/")
    content = response.content.decode()

    assert 'id="graphique-steps"' in content
    assert 'id="graphique-weight"' not in content
    assert 'id="graphique-volume"' not in content
    assert 'id="graphique-pace"' not in content


def test_aucun_graphique_n_est_encadre_si_rien_n_a_de_donnee_sur_la_periode(logged_client, user):
    # Une mesure existe (has_data=True, pas d'état vide) mais hors de la
    # période filtrée : aucun des quatre graphiques n'a de série à montrer.
    WeightMeasurement.objects.create(
        user=user, recorded_at=timezone.now() - timedelta(days=100), weight_kg="80.0"
    )

    response = logged_client.get("/sante/", {"periode": "7"})
    content = response.content.decode()

    assert "Aucune donnée importée" not in content
    assert "Pas par jour" not in content
    assert "Poids</p>" not in content
