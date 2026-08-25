from datetime import timedelta

import pytest
from django.db import IntegrityError
from django.utils import timezone

from health.models import Activity, WeightMeasurement

pytestmark = pytest.mark.django_db


def test_une_mesure_de_poids_se_cree_et_s_affiche(user):
    measurement = WeightMeasurement.objects.create(
        user=user, recorded_at=timezone.now(), weight_kg="82.30", source="Santé"
    )
    assert "82.30 kg" in str(measurement)


def test_deux_mesures_au_meme_instant_sont_refusees(user):
    instant = timezone.now()
    WeightMeasurement.objects.create(user=user, recorded_at=instant, weight_kg="82.0")
    with pytest.raises(IntegrityError):
        WeightMeasurement.objects.create(user=user, recorded_at=instant, weight_kg="83.0")


def test_une_activite_calcule_sa_duree_et_son_allure(user):
    started = timezone.now()
    activity = Activity.objects.create(
        user=user,
        activity_type=Activity.ActivityType.RUNNING,
        started_at=started,
        ended_at=started + timedelta(minutes=30),
        distance_meters=5000,
    )
    assert activity.duration_seconds == 1800
    assert activity.pace_seconds_per_km == pytest.approx(360)
    assert activity.pace_label == "6:00 /km"


def test_une_activite_sans_distance_n_a_pas_d_allure(user):
    started = timezone.now()
    activity = Activity.objects.create(
        user=user,
        activity_type=Activity.ActivityType.STRENGTH_TRAINING,
        started_at=started,
        ended_at=started + timedelta(minutes=45),
    )
    assert activity.pace_seconds_per_km is None
    assert activity.pace_label is None
    assert activity.distance_km_label is None


def test_deux_activites_du_meme_type_au_meme_debut_sont_refusees(user):
    started = timezone.now()
    Activity.objects.create(
        user=user,
        activity_type=Activity.ActivityType.RUNNING,
        started_at=started,
        ended_at=started + timedelta(minutes=30),
    )
    with pytest.raises(IntegrityError):
        Activity.objects.create(
            user=user,
            activity_type=Activity.ActivityType.RUNNING,
            started_at=started,
            ended_at=started + timedelta(minutes=20),
        )
