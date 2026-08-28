from datetime import timedelta

import pytest
from django.http import QueryDict
from django.utils import timezone

from health import filters
from health.models import Activity, DailySteps

pytestmark = pytest.mark.django_db


def _activity(user, activity_type, days_ago=0, source=""):
    now = timezone.now()
    return Activity.objects.create(
        user=user,
        activity_type=activity_type,
        started_at=now - timedelta(days=days_ago),
        ended_at=now - timedelta(days=days_ago) + timedelta(minutes=20),
        source=source,
    )


def test_plusieurs_types_coches_se_cumulent_en_ou(user):
    _activity(user, Activity.ActivityType.RUNNING)
    _activity(user, Activity.ActivityType.CYCLING)
    _activity(user, Activity.ActivityType.SWIMMING)

    params = QueryDict("type=running&type=cycling")
    result = filters.filter_activities(params, user)

    assert {a.activity_type for a in result} == {"running", "cycling"}


def test_type_et_periode_se_cumulent_en_et(user):
    _activity(user, Activity.ActivityType.RUNNING, days_ago=1)
    _activity(user, Activity.ActivityType.RUNNING, days_ago=100)
    _activity(user, Activity.ActivityType.CYCLING, days_ago=1)

    params = QueryDict("type=running&periode=7")
    result = filters.filter_activities(params, user)

    assert result.count() == 1
    assert result.first().activity_type == Activity.ActivityType.RUNNING


def test_une_valeur_de_periode_inconnue_retombe_sur_la_valeur_par_defaut():
    value, days = filters.selected_period(QueryDict("periode=999"))
    assert value == filters.DEFAULT_PERIOD
    assert days == 30


def test_periode_tout_ne_filtre_rien(user):
    _activity(user, Activity.ActivityType.RUNNING, days_ago=1000)

    params = QueryDict("periode=tout")
    assert filters.filter_activities(params, user).count() == 1


def test_filter_daily_steps_respecte_la_periode(user):
    today = timezone.now().date()
    DailySteps.objects.create(user=user, date=today, steps=8000)
    DailySteps.objects.create(user=user, date=today - timedelta(days=100), steps=9000)

    params = QueryDict("periode=7")
    result = filters.filter_daily_steps(params, user)

    assert result.count() == 1
    assert result.first().steps == 8000


def test_has_active_filters_detecte_un_type_ou_une_periode_non_par_defaut():
    empty_group = filters.build_type_group(QueryDict())
    assert filters.has_active_filters(empty_group, QueryDict()) is False
    assert filters.has_active_filters(empty_group, QueryDict("periode=7")) is True

    chosen_group = filters.build_type_group(QueryDict("type=running"))
    assert filters.has_active_filters(chosen_group, QueryDict("type=running")) is True


def test_la_recherche_filtre_sur_la_source(user):
    _activity(user, Activity.ActivityType.RUNNING, source="Montre Garmin")
    _activity(user, Activity.ActivityType.CYCLING, source="iPhone")

    params = QueryDict("q=garmin")
    result = filters.filter_activities(params, user)

    assert result.count() == 1
    assert result.first().source == "Montre Garmin"


def test_la_recherche_filtre_sur_le_libelle_traduit_du_type(user):
    _activity(user, Activity.ActivityType.RUNNING)
    _activity(user, Activity.ActivityType.CYCLING)

    params = QueryDict("q=course")
    result = filters.filter_activities(params, user)

    assert result.count() == 1
    assert result.first().activity_type == Activity.ActivityType.RUNNING


def test_la_recherche_se_cumule_avec_les_autres_criteres(user):
    _activity(user, Activity.ActivityType.RUNNING, days_ago=1, source="Garmin")
    _activity(user, Activity.ActivityType.RUNNING, days_ago=100, source="Garmin")

    params = QueryDict("q=garmin&periode=7")
    result = filters.filter_activities(params, user)

    assert result.count() == 1


def test_une_recherche_vide_ou_blanche_ne_filtre_rien(user):
    _activity(user, Activity.ActivityType.RUNNING)
    _activity(user, Activity.ActivityType.CYCLING)

    assert filters.filter_activities(QueryDict("q="), user).count() == 2
    assert filters.filter_activities(QueryDict("q=%20%20"), user).count() == 2


def test_has_active_filters_detecte_une_recherche():
    empty_group = filters.build_type_group(QueryDict())
    assert filters.has_active_filters(empty_group, QueryDict("q=garmin")) is True
