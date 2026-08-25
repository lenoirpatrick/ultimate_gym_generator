from datetime import timedelta

import pytest
from django.http import QueryDict
from django.utils import timezone

from health import filters
from health.models import Activity

pytestmark = pytest.mark.django_db


def _activity(user, activity_type, days_ago=0):
    now = timezone.now()
    return Activity.objects.create(
        user=user,
        activity_type=activity_type,
        started_at=now - timedelta(days=days_ago),
        ended_at=now - timedelta(days=days_ago) + timedelta(minutes=20),
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


def test_has_active_filters_detecte_un_type_ou_une_periode_non_par_defaut():
    empty_group = filters.build_type_group(QueryDict())
    assert filters.has_active_filters(empty_group, QueryDict()) is False
    assert filters.has_active_filters(empty_group, QueryDict("periode=7")) is True

    chosen_group = filters.build_type_group(QueryDict("type=running"))
    assert filters.has_active_filters(chosen_group, QueryDict("type=running")) is True
