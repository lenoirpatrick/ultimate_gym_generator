from datetime import date, timedelta

import pytest
from django.db import IntegrityError
from django.utils import timezone

from health.models import Activity, ApiKey, DailySteps, ExcludedImport, WeightMeasurement

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


def test_une_duree_explicite_prime_sur_l_ecart_horaire(user):
    # Issue #79 : une durée active connue (import HealthKit) doit primer sur
    # l'écart started_at/ended_at, qui inclut les pauses.
    started = timezone.now()
    activity = Activity.objects.create(
        user=user,
        activity_type=Activity.ActivityType.RUNNING,
        started_at=started,
        ended_at=started + timedelta(minutes=30),
        duration_seconds=600,
        distance_meters=2000,
    )
    assert activity.duration_seconds == 600
    assert activity.pace_label == "5:00 /km"


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


def test_un_total_de_pas_se_cree_et_s_affiche(user):
    total = DailySteps.objects.create(user=user, date=date(2024, 1, 1), steps=8500)
    assert "8500 pas" in str(total)


def test_deux_totaux_de_pas_le_meme_jour_sont_refuses(user):
    DailySteps.objects.create(user=user, date=date(2024, 1, 1), steps=8500)
    with pytest.raises(IntegrityError):
        DailySteps.objects.create(user=user, date=date(2024, 1, 1), steps=100)


def test_une_exclusion_ne_se_double_pas_pour_la_meme_cle(user):
    ExcludedImport.objects.create(
        user=user,
        kind=ExcludedImport.Kind.ACTIVITY,
        natural_key="running|2024-01-01T08:00:00+00:00",
    )
    with pytest.raises(IntegrityError):
        ExcludedImport.objects.create(
            user=user,
            kind=ExcludedImport.Kind.ACTIVITY,
            natural_key="running|2024-01-01T08:00:00+00:00",
        )


def test_une_cle_api_generee_n_expose_jamais_le_secret_en_clair(user):
    api_key, raw_key = ApiKey.generate(user, "iPhone — Raccourci")
    assert api_key.hashed_key != raw_key
    assert api_key.prefix == raw_key[:8]
    assert api_key.matches(raw_key)
    assert not api_key.matches("une-autre-valeur")
