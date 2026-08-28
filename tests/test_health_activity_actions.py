from datetime import timedelta

import pytest
from django.utils import timezone

from health.models import Activity, ExcludedImport

pytestmark = pytest.mark.django_db


def test_supprimer_une_activite_l_efface_et_l_exclut(logged_client, user):
    now = timezone.now()
    activity = Activity.objects.create(
        user=user,
        activity_type=Activity.ActivityType.RUNNING,
        started_at=now,
        ended_at=now + timedelta(minutes=30),
    )

    response = logged_client.post(f"/sante/activites/{activity.pk}/supprimer/")

    assert response.status_code == 200
    assert not Activity.objects.filter(pk=activity.pk).exists()
    assert ExcludedImport.objects.filter(user=user, kind=ExcludedImport.Kind.ACTIVITY).exists()


def test_supprimer_une_activite_rend_la_vue_filtree_courante(logged_client, user):
    now = timezone.now()
    running = Activity.objects.create(
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

    response = logged_client.post(f"/sante/activites/{running.pk}/supprimer/", {"type": "cycling"})
    content = response.content.decode()

    assert ">Vélo</p>" in content
    assert ">Course à pied</p>" not in content


def test_supprimer_l_activite_d_un_autre_utilisateur_est_refuse(logged_client, django_user_model):
    other = django_user_model.objects.create_user(email="autre@example.test", password="x")
    now = timezone.now()
    activity = Activity.objects.create(
        user=other,
        activity_type=Activity.ActivityType.RUNNING,
        started_at=now,
        ended_at=now + timedelta(minutes=30),
    )

    response = logged_client.post(f"/sante/activites/{activity.pk}/supprimer/")

    assert response.status_code == 404
    assert Activity.objects.filter(pk=activity.pk).exists()


def test_reimporter_apres_suppression_ne_recree_pas_l_activite(logged_client, user):
    now = timezone.now()
    activity = Activity.objects.create(
        user=user,
        activity_type=Activity.ActivityType.RUNNING,
        started_at=now,
        ended_at=now + timedelta(minutes=30),
    )

    logged_client.post(f"/sante/activites/{activity.pk}/supprimer/")

    from health import ingest

    created = ingest.upsert_activity(
        user,
        activity_type=Activity.ActivityType.RUNNING,
        started_at=now,
        ended_at=now + timedelta(minutes=30),
    )

    assert created is None
    assert not Activity.objects.filter(user=user).exists()


def test_modifier_le_type_change_l_activite_et_exclut_l_ancienne_cle(logged_client, user):
    now = timezone.now()
    activity = Activity.objects.create(
        user=user,
        activity_type=Activity.ActivityType.RUNNING,
        started_at=now,
        ended_at=now + timedelta(minutes=30),
    )

    response = logged_client.post(
        f"/sante/activites/{activity.pk}/type/", {"activity_type": "cycling"}
    )
    activity.refresh_from_db()

    assert response.status_code == 200
    assert activity.activity_type == Activity.ActivityType.CYCLING
    assert ExcludedImport.objects.filter(
        user=user, kind=ExcludedImport.Kind.ACTIVITY, natural_key__startswith="running|"
    ).exists()


def test_reimporter_apres_modification_du_type_ne_recree_pas_l_ancien_type(logged_client, user):
    now = timezone.now()
    activity = Activity.objects.create(
        user=user,
        activity_type=Activity.ActivityType.RUNNING,
        started_at=now,
        ended_at=now + timedelta(minutes=30),
    )

    logged_client.post(f"/sante/activites/{activity.pk}/type/", {"activity_type": "cycling"})

    from health import ingest

    created = ingest.upsert_activity(
        user,
        activity_type=Activity.ActivityType.RUNNING,
        started_at=now,
        ended_at=now + timedelta(minutes=30),
    )

    assert created is None
    assert Activity.objects.filter(user=user).count() == 1
    assert Activity.objects.get(user=user).activity_type == Activity.ActivityType.CYCLING


def test_un_type_invalide_ne_modifie_rien(logged_client, user):
    now = timezone.now()
    activity = Activity.objects.create(
        user=user,
        activity_type=Activity.ActivityType.RUNNING,
        started_at=now,
        ended_at=now + timedelta(minutes=30),
    )

    response = logged_client.post(
        f"/sante/activites/{activity.pk}/type/", {"activity_type": "n_importe_quoi"}
    )
    activity.refresh_from_db()

    assert response.status_code == 200
    assert activity.activity_type == Activity.ActivityType.RUNNING
    assert not ExcludedImport.objects.filter(user=user).exists()
