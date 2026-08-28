from datetime import UTC, datetime, timedelta
from datetime import timezone as dt_timezone

import pytest

from health import exclusions
from health.models import Activity, ExcludedImport, WeightMeasurement

pytestmark = pytest.mark.django_db


def test_la_cle_est_stable_quel_que_soit_le_fuseau_d_origine(user):
    # Le même instant, porté par deux fuseaux différents, doit produire la
    # même clé — sans quoi une entrée relue depuis la base (toujours en UTC)
    # ne matcherait plus la clé calculée au moment de l'import.
    paris = datetime(2024, 1, 1, 9, 0, 0, tzinfo=dt_timezone(timedelta(hours=1)))
    utc = datetime(2024, 1, 1, 8, 0, 0, tzinfo=UTC)

    assert exclusions.weight_key(paris) == exclusions.weight_key(utc)


def test_exclure_puis_verifier_un_poids(user):
    instant = datetime(2024, 1, 1, 8, 0, 0, tzinfo=UTC)

    assert not exclusions.is_weight_excluded(user, instant)

    exclusions.exclude_weight(user, instant)

    assert exclusions.is_weight_excluded(user, instant)
    assert ExcludedImport.objects.filter(user=user, kind=ExcludedImport.Kind.WEIGHT).count() == 1


def test_exclure_deux_fois_le_meme_poids_ne_duplique_rien(user):
    instant = datetime(2024, 1, 1, 8, 0, 0, tzinfo=UTC)

    exclusions.exclude_weight(user, instant)
    exclusions.exclude_weight(user, instant)

    assert ExcludedImport.objects.filter(user=user).count() == 1


def test_exclure_une_activite_ne_s_applique_pas_a_un_autre_type(user):
    started = datetime(2024, 1, 1, 8, 0, 0, tzinfo=UTC)

    exclusions.exclude_activity(user, Activity.ActivityType.RUNNING, started)

    assert exclusions.is_activity_excluded(user, Activity.ActivityType.RUNNING, started)
    assert not exclusions.is_activity_excluded(user, Activity.ActivityType.CYCLING, started)


def test_reimporter_un_poids_exclu_ne_le_recree_pas(user):
    from health import ingest

    instant = datetime(2024, 1, 1, 8, 0, 0, tzinfo=UTC)
    exclusions.exclude_weight(user, instant)

    created = ingest.upsert_weight(user, instant, "80.0")

    assert created is None
    assert not WeightMeasurement.objects.filter(user=user).exists()
