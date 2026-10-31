"""Aperçu Home Assistant sur l'écran de séance : cartes, actions, états (issue #133).

Aucun appel réseau réel : le client reçoit un `httpx.MockTransport`.
"""

import httpx
import pytest
from django.urls import reverse

from exercises.models import Exercise
from homeassistant.client import HomeAssistantClient
from homeassistant.models import Connection, Entity
from workouts.models import Workout, WorkoutExercise

pytestmark = pytest.mark.django_db


@pytest.fixture
def ha_connection():
    return Connection.objects.create(base_url="http://ha.test:8123", token="jeton")


@pytest.fixture
def ventilateur():
    return Entity.objects.create(entity_id="switch.ventilateur", label="Ventilateur")


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


@pytest.fixture
def home_assistant(monkeypatch):
    """Instance factice : un ventilateur dont l'état suit les appels de service."""
    house = {"state": "off", "calls": []}

    def respond(request):
        if request.method == "POST":
            service = request.url.path.rsplit("/", 1)[-1]
            house["calls"].append(service)
            house["state"] = "on" if service == "turn_on" else "off"
            return httpx.Response(200, json=[])
        return httpx.Response(200, json={"state": house["state"], "attributes": {}})

    monkeypatch.setattr(HomeAssistantClient, "transport", httpx.MockTransport(respond))
    return house


def detail(client, workout) -> str:
    return client.get(reverse("workouts:detail", args=[workout.pk])).content.decode()


def test_l_ecran_de_seance_montre_les_entites_en_apercu(
    logged_client, workout, ha_connection, ventilateur
):
    Entity.objects.create(
        entity_id="sensor.temperature", label="Température", show_on_workout=False
    )

    content = detail(logged_client, workout)

    # Chaque carte charge son état après l'affichage de l'écran.
    assert reverse("homeassistant:entity", args=[ventilateur.pk]) in content
    assert 'hx-trigger="load"' in content
    assert "Température" not in content


def test_pas_d_apercu_sans_connexion(logged_client, workout, ventilateur):
    assert reverse("homeassistant:entity", args=[ventilateur.pk]) not in detail(
        logged_client, workout
    )


def test_pas_d_apercu_sans_entite_a_afficher(logged_client, workout, ha_connection):
    assert 'id="seance-maison-titre"' not in detail(logged_client, workout)


def test_une_carte_exige_une_authentification(client, ventilateur):
    assert client.get(reverse("homeassistant:entity", args=[ventilateur.pk])).status_code == 302


def test_la_carte_charge_l_etat_et_l_action_utile(
    logged_client, ha_connection, ventilateur, home_assistant
):
    content = logged_client.get(
        reverse("homeassistant:entity", args=[ventilateur.pk])
    ).content.decode()

    assert "Éteint" in content
    assert reverse("homeassistant:action", args=[ventilateur.pk, "turn_on"]) in content
    assert reverse("homeassistant:action", args=[ventilateur.pk, "turn_off"]) not in content


def test_une_action_s_execute_et_relit_l_etat(
    logged_client, ha_connection, ventilateur, home_assistant
):
    url = reverse("homeassistant:action", args=[ventilateur.pk, "turn_on"])

    content = logged_client.post(url).content.decode()

    assert home_assistant["calls"] == ["turn_on"]
    assert "Allumé" in content
    assert reverse("homeassistant:action", args=[ventilateur.pk, "turn_off"]) in content


def test_un_service_hors_du_domaine_est_refuse(
    logged_client, ha_connection, ventilateur, home_assistant
):
    url = reverse("homeassistant:action", args=[ventilateur.pk, "unlock"])

    response = logged_client.post(url)

    assert response.status_code == 400
    assert home_assistant["calls"] == []


def test_un_capteur_n_accepte_aucune_action(logged_client, ha_connection, home_assistant):
    capteur = Entity.objects.create(entity_id="sensor.temperature", label="Température")

    response = logged_client.post(reverse("homeassistant:action", args=[capteur.pk, "turn_on"]))

    assert response.status_code == 400


def test_une_panne_reste_sur_la_carte(logged_client, ha_connection, ventilateur, monkeypatch):
    def refuse(request):
        raise httpx.ConnectError("refusé", request=request)

    monkeypatch.setattr(HomeAssistantClient, "transport", httpx.MockTransport(refuse))

    response = logged_client.get(reverse("homeassistant:entity", args=[ventilateur.pk]))
    content = response.content.decode()

    assert response.status_code == 200
    assert "injoignable" in content
    assert "Réessayer" in content


def test_une_action_echouee_le_dit(logged_client, ha_connection, ventilateur, monkeypatch):
    monkeypatch.setattr(
        HomeAssistantClient,
        "transport",
        httpx.MockTransport(lambda request: httpx.Response(401)),
    )

    url = reverse("homeassistant:action", args=[ventilateur.pk, "turn_on"])
    content = logged_client.post(url).content.decode()

    assert "Action impossible" in content


def test_une_action_exige_une_requete_post(logged_client, ha_connection, ventilateur):
    url = reverse("homeassistant:action", args=[ventilateur.pk, "turn_on"])

    assert logged_client.get(url).status_code == 405


def test_la_carte_compacte_garde_sa_variante(
    logged_client, ha_connection, ventilateur, home_assistant
):
    url = reverse("homeassistant:entity", args=[ventilateur.pk]) + "?compact=1"

    content = logged_client.get(url).content.decode()

    assert "ugg-ha-entity--compact" in content
    assert f'id="ha-entite-{ventilateur.pk}-minuteur"' in content
    # Pendant une séance, la carte se relit d'elle-même toutes les minutes.
    assert 'hx-trigger="every 60s"' in content


def test_la_carte_de_l_apercu_ne_se_relit_pas_seule(
    logged_client, ha_connection, ventilateur, home_assistant
):
    content = logged_client.get(
        reverse("homeassistant:entity", args=[ventilateur.pk])
    ).content.decode()

    assert "every 60s" not in content
