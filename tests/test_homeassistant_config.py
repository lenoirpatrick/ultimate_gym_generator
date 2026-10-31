"""Home Assistant : connexion, entités suivies, client REST (issue #132).

Aucun appel réseau réel : le client reçoit un `httpx.MockTransport`.
"""

import httpx
import pytest
from django.db import connection as db_connection
from django.urls import reverse

from homeassistant.client import HomeAssistantClient, HomeAssistantError
from homeassistant.models import MAX_ENTITIES, Connection, Entity

pytestmark = pytest.mark.django_db


@pytest.fixture
def ha_connection():
    return Connection.objects.create(base_url="http://ha.test:8123/", token="jeton-secret")


@pytest.fixture
def transport(monkeypatch):
    """Installe un répondeur HTTP factice ; renvoie la liste des requêtes reçues."""
    requests: list[httpx.Request] = []

    def install(responder):
        def record(request):
            requests.append(request)
            return responder(request)

        monkeypatch.setattr(HomeAssistantClient, "transport", httpx.MockTransport(record))
        return requests

    return install


def entity_payload(rows: list[dict], initial: int = 0) -> dict:
    data = {
        "form-TOTAL_FORMS": str(len(rows)),
        "form-INITIAL_FORMS": str(initial),
        "form-MIN_NUM_FORMS": "0",
        "form-MAX_NUM_FORMS": str(MAX_ENTITIES),
    }
    for index, row in enumerate(rows):
        for key, value in row.items():
            data[f"form-{index}-{key}"] = value
    return data


# --------------------------------------------------------------------------- #
# Modèle
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("entity_id", "services"),
    [
        ("switch.ventilateur", ["turn_on", "turn_off"]),
        ("light.salle", ["turn_on", "turn_off"]),
        ("scene.echauffement", ["turn_on"]),
        ("button.porte", ["press"]),
        ("sensor.temperature", []),
        ("binary_sensor.porte", []),
    ],
)
def test_les_actions_decoulent_du_domaine(entity_id, services):
    entity = Entity(entity_id=entity_id, label="x")

    assert [action.service for action in entity.actions] == services


@pytest.mark.parametrize(
    ("state", "services"),
    [("on", ["turn_off"]), ("off", ["turn_on"]), ("unavailable", ["turn_on", "turn_off"])],
)
def test_seule_l_action_qui_change_l_etat_est_proposee(state, services):
    entity = Entity(entity_id="switch.ventilateur", label="Ventilateur")

    assert [action.service for action in entity.actions_for(state)] == services


def test_le_jeton_est_chiffre_en_base(ha_connection):
    with db_connection.cursor() as cursor:
        cursor.execute("SELECT token FROM homeassistant_connection")
        stored = cursor.fetchone()[0]

    assert "jeton-secret" not in stored
    assert Connection.load().token == "jeton-secret"


# --------------------------------------------------------------------------- #
# Client
# --------------------------------------------------------------------------- #


def test_le_client_lit_l_etat_et_l_unite(ha_connection, transport):
    requests = transport(
        lambda request: httpx.Response(
            200,
            json={"state": "21.5", "attributes": {"unit_of_measurement": "°C"}},
        )
    )

    state = HomeAssistantClient(ha_connection).state("sensor.temperature")

    assert state.display == "21.5 °C"
    assert str(requests[0].url) == "http://ha.test:8123/api/states/sensor.temperature"
    assert requests[0].headers["Authorization"] == "Bearer jeton-secret"


def test_le_client_appelle_le_service_du_domaine(ha_connection, transport):
    requests = transport(lambda request: httpx.Response(200, json=[]))

    HomeAssistantClient(ha_connection).call("switch.ventilateur", "toggle")

    assert requests[0].method == "POST"
    assert requests[0].url.path == "/api/services/switch/toggle"
    assert requests[0].content == b'{"entity_id":"switch.ventilateur"}'


@pytest.mark.parametrize(
    ("status", "message"),
    [(401, "Jeton d'accès refusé"), (404, "Entité inconnue"), (500, "erreur 500")],
)
def test_le_client_traduit_les_erreurs_http(ha_connection, transport, status, message):
    transport(lambda request: httpx.Response(status))

    with pytest.raises(HomeAssistantError, match=message):
        HomeAssistantClient(ha_connection).state("sensor.x")


def test_le_client_signale_une_instance_injoignable(ha_connection, transport):
    def refuse(request):
        raise httpx.ConnectError("refusé", request=request)

    transport(refuse)

    with pytest.raises(HomeAssistantError, match="injoignable"):
        HomeAssistantClient(ha_connection).ping()


# --------------------------------------------------------------------------- #
# Écran de configuration
# --------------------------------------------------------------------------- #


def test_la_configuration_est_reservee_au_personnel(logged_client):
    assert logged_client.get(reverse("homeassistant:settings")).status_code == 302


def test_le_personnel_accede_a_la_configuration(staff_client):
    response = staff_client.get(reverse("homeassistant:settings"))

    assert response.status_code == 200
    assert "Entités suivies" in response.content.decode()


def test_la_connexion_et_une_entite_s_enregistrent(staff_client):
    payload = {"base_url": "http://ha.test:8123", "token": "jeton"} | entity_payload(
        [{"entity_id": "switch.ventilateur", "label": "Ventilateur", "show_in_timer": "on"}]
    )

    response = staff_client.post(reverse("homeassistant:settings"), payload)

    assert response.status_code == 302
    entity = Entity.objects.get()
    assert entity.label == "Ventilateur"
    assert entity.show_on_workout is False
    assert entity.show_in_timer is True
    assert Connection.load().token == "jeton"


def test_un_jeton_laisse_vide_est_conserve(staff_client, ha_connection):
    payload = {"base_url": "http://ha.test:8123", "token": ""} | entity_payload([])

    staff_client.post(reverse("homeassistant:settings"), payload)

    assert Connection.load().token == "jeton-secret"


def test_le_jeton_est_obligatoire_a_la_premiere_connexion(staff_client):
    payload = {"base_url": "http://ha.test:8123", "token": ""} | entity_payload([])

    response = staff_client.post(reverse("homeassistant:settings"), payload)

    assert response.status_code == 200
    assert Connection.load() is None


def test_un_identifiant_mal_forme_est_refuse(staff_client, ha_connection):
    payload = {"base_url": "http://ha.test:8123"} | entity_payload(
        [{"entity_id": "Ventilateur", "label": "Ventilateur", "show_on_workout": "on"}]
    )

    response = staff_client.post(reverse("homeassistant:settings"), payload)

    assert response.status_code == 200
    assert "Identifiant Home Assistant attendu" in response.content.decode()
    assert not Entity.objects.exists()


def test_pas_plus_de_cinq_entites(staff_client, ha_connection):
    rows = [
        {"entity_id": f"sensor.capteur_{n}", "label": f"Capteur {n}", "show_on_workout": "on"}
        for n in range(MAX_ENTITIES + 1)
    ]
    payload = {"base_url": "http://ha.test:8123"} | entity_payload(rows)

    response = staff_client.post(reverse("homeassistant:settings"), payload)

    assert response.status_code == 200
    assert not Entity.objects.exists()


def test_une_entite_cesse_d_etre_suivie(staff_client, ha_connection):
    entity = Entity.objects.create(entity_id="switch.ventilateur", label="Ventilateur")
    payload = {"base_url": "http://ha.test:8123"} | entity_payload(
        [
            {
                "id": str(entity.pk),
                "entity_id": "switch.ventilateur",
                "label": "Ventilateur",
                "DELETE": "on",
            }
        ],
        initial=1,
    )

    staff_client.post(reverse("homeassistant:settings"), payload)

    assert not Entity.objects.exists()


def test_le_test_de_connexion_sans_configuration_le_dit(staff_client):
    response = staff_client.post(reverse("homeassistant:test"))

    assert "Enregistre d&#x27;abord" in response.content.decode()


def test_le_test_de_connexion_reussit(staff_client, ha_connection, transport):
    transport(lambda request: httpx.Response(200, json={"message": "API running."}))

    response = staff_client.post(reverse("homeassistant:test"))

    assert "Connexion établie" in response.content.decode()


def test_le_test_de_connexion_signale_un_jeton_refuse(staff_client, ha_connection, transport):
    transport(lambda request: httpx.Response(401))

    response = staff_client.post(reverse("homeassistant:test"))

    assert "Jeton d&#x27;accès refusé" in response.content.decode()


def test_le_menu_configuration_propose_home_assistant_au_personnel(staff_client, logged_client):
    url = reverse("homeassistant:settings")

    assert url in staff_client.get(reverse("accounts:profile")).content.decode()
    assert url not in logged_client.get(reverse("accounts:profile")).content.decode()
