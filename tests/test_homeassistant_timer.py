"""Bandeau Maison dans le minuteur de séance (issue #134)."""

import pytest
from django.urls import reverse

from exercises.models import Exercise
from homeassistant.models import Connection, Entity, timer_enabled
from workouts.models import Workout, WorkoutExercise

pytestmark = pytest.mark.django_db


@pytest.fixture
def ha_connection():
    return Connection.objects.create(base_url="http://ha.test:8123", token="jeton")


@pytest.fixture
def ventilateur():
    return Entity.objects.create(
        entity_id="switch.ventilateur",
        label="Ventilateur",
        show_on_workout=False,
        show_in_timer=True,
    )


@pytest.fixture
def workout(user):
    workout = Workout.objects.create(
        user=user,
        duration_minutes=Workout.Duration.THIRTY,
        format=Workout.Format.CIRCUIT,
        planned_seconds=600,
    )
    WorkoutExercise.objects.create(
        workout=workout,
        position=1,
        block_index=0,
        block_label="Bloc 1",
        exercise=Exercise.objects.get(slug="Barbell_Squat"),
        rounds=3,
        reps=[10, 10, 10],
        rest_seconds=60,
    )
    return workout


def detail(client, workout) -> str:
    return client.get(reverse("workouts:detail", args=[workout.pk])).content.decode()


def test_le_bandeau_exige_une_connexion_et_une_entite(ha_connection, ventilateur):
    assert timer_enabled() is True


def test_sans_connexion_pas_de_bandeau(ventilateur):
    assert timer_enabled() is False


def test_sans_entite_pour_le_minuteur_pas_de_bandeau(ha_connection):
    Entity.objects.create(entity_id="switch.ventilateur", label="V", show_in_timer=False)

    assert timer_enabled() is False


def test_le_minuteur_prevoit_le_bandeau(logged_client, workout, ha_connection, ventilateur):
    content = detail(logged_client, workout)

    assert 'id="minuteur-maison"' in content
    assert reverse("homeassistant:timer") in content
    # Chargé à l'ouverture du minuteur, jamais avec la page.
    assert 'hx-trigger="minuteur-ouvert from:body"' in content
    assert reverse("homeassistant:entity", args=[ventilateur.pk]) not in content


def test_le_minuteur_n_a_pas_de_bandeau_sans_home_assistant(logged_client, workout):
    assert 'id="minuteur-maison"' not in detail(logged_client, workout)


def test_le_bandeau_rend_des_cartes_compactes(logged_client, ha_connection, ventilateur):
    Entity.objects.create(entity_id="light.salle", label="Lumière", show_in_timer=False)

    content = logged_client.get(reverse("homeassistant:timer")).content.decode()

    assert "ugg-ha-entity--compact" in content
    assert reverse("homeassistant:entity", args=[ventilateur.pk]) + "?compact=1" in content
    assert "Lumière" not in content


def test_le_bandeau_est_vide_sans_configuration(logged_client, ventilateur):
    response = logged_client.get(reverse("homeassistant:timer"))

    assert response.status_code == 200
    assert response.content == b""


def test_le_bandeau_exige_une_authentification(client):
    assert client.get(reverse("homeassistant:timer")).status_code == 302
