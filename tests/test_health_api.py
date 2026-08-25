import json

import pytest

from health.models import ApiKey

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_key(user):
    return ApiKey.generate(user, "Test")


def _post(client, raw_key, payload):
    return client.post(
        "/sante/api/ingestion/",
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {raw_key}" if raw_key else "",
    )


def test_ingestion_sans_cle_est_refusee(client):
    response = _post(client, None, {"weights": []})
    assert response.status_code == 401


def test_ingestion_avec_une_cle_invalide_est_refusee(client):
    response = _post(client, "clef-inexistante-1234", {"weights": []})
    assert response.status_code == 401


def test_ingestion_valide_cree_poids_et_activites(client, user, api_key):
    _instance, raw_key = api_key
    payload = {
        "weights": [{"recorded_at": "2024-01-01T08:00:00+01:00", "weight_kg": 82.3}],
        "activities": [
            {
                "activity_type": "running",
                "started_at": "2024-01-02T07:00:00+01:00",
                "ended_at": "2024-01-02T07:32:30+01:00",
                "distance_meters": 5200,
            }
        ],
    }

    response = _post(client, raw_key, payload)

    assert response.status_code == 200
    data = response.json()
    assert data["weights_created"] == 1
    assert data["activities_created"] == 1
    assert data["errors"] == []

    _instance.refresh_from_db()
    assert _instance.last_used_at is not None


def test_ingestion_idempotente_sur_le_meme_envoi(client, user, api_key):
    _instance, raw_key = api_key
    payload = {"weights": [{"recorded_at": "2024-01-01T08:00:00+01:00", "weight_kg": 82.3}]}

    _post(client, raw_key, payload)
    response = _post(client, raw_key, payload)

    assert response.json()["weights_created"] == 0
    assert response.json()["weights_updated"] == 1


def test_une_entree_invalide_n_empeche_pas_les_autres(client, user, api_key):
    _instance, raw_key = api_key
    payload = {
        "weights": [
            {"recorded_at": "2024-01-01T08:00:00+01:00", "weight_kg": 82.3},
            {"recorded_at": "pas-une-date", "weight_kg": 80},
        ]
    }

    response = _post(client, raw_key, payload)

    assert response.status_code == 200
    data = response.json()
    assert data["weights_created"] == 1
    assert len(data["errors"]) == 1


def test_un_type_d_activite_inconnu_tombe_sur_autre(client, user, api_key):
    _instance, raw_key = api_key
    payload = {
        "activities": [
            {
                "activity_type": "trampoline",
                "started_at": "2024-01-02T07:00:00+01:00",
                "ended_at": "2024-01-02T07:30:00+01:00",
            }
        ]
    }

    response = _post(client, raw_key, payload)

    assert response.status_code == 200
    assert response.json()["activities_created"] == 1


def test_creation_et_revocation_d_une_cle(logged_client):
    response = logged_client.post("/sante/cles-api/", data={"label": "iPhone"})
    assert response.status_code == 200
    assert "conserve-la" in response.content.decode().lower() or ApiKey.objects.exists()

    key = ApiKey.objects.get()
    response = logged_client.post(f"/sante/cles-api/{key.pk}/revoquer/")
    assert response.status_code == 200
    assert not ApiKey.objects.filter(pk=key.pk).exists()
