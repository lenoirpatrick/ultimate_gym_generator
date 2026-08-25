from io import BytesIO
from pathlib import Path

import pytest

from health.importer import ExportParseError, parse_export
from health.models import Activity, WeightMeasurement

pytestmark = pytest.mark.django_db

FIXTURE = Path(__file__).parent / "fixtures" / "health_export.xml"


def _fixture_bytes() -> bytes:
    return FIXTURE.read_bytes()


def test_un_export_valide_importe_poids_et_activites(user):
    result = parse_export(user, BytesIO(_fixture_bytes()))

    assert result.weights_created == 2
    assert result.weights_updated == 0
    assert result.activities_created == 2
    assert result.activities_updated == 0
    assert WeightMeasurement.objects.filter(user=user).count() == 2
    assert Activity.objects.filter(user=user).count() == 2


def test_un_poids_en_livres_est_converti_en_kilogrammes(user):
    parse_export(user, BytesIO(_fixture_bytes()))
    converted = WeightMeasurement.objects.get(user=user, weight_kg="81.65")
    assert converted.source == "Santé"


def test_un_type_d_activite_inconnu_est_importe_comme_autre(user):
    result = parse_export(user, BytesIO(_fixture_bytes()))

    assert "HKWorkoutActivityTypeCurling" in result.skipped_types
    other = Activity.objects.get(user=user, activity_type=Activity.ActivityType.OTHER)
    # Énergie repliée sur les <WorkoutStatistics> (kJ convertis en kcal), aucun
    # attribut totalEnergyBurned direct sur ce <Workout> de la fixture.
    assert other.active_energy_kcal == pytest.approx(410 / 4.184)


def test_le_running_lit_la_distance_et_la_frequence_cardiaque(user):
    parse_export(user, BytesIO(_fixture_bytes()))
    run = Activity.objects.get(user=user, activity_type=Activity.ActivityType.RUNNING)
    assert run.distance_meters == pytest.approx(5200)
    assert run.average_heart_rate == 148


def test_reimporter_le_meme_fichier_ne_duplique_rien(user):
    parse_export(user, BytesIO(_fixture_bytes()))
    result = parse_export(user, BytesIO(_fixture_bytes()))

    assert result.weights_created == 0
    assert result.weights_updated == 2
    assert result.activities_created == 0
    assert result.activities_updated == 2
    assert WeightMeasurement.objects.filter(user=user).count() == 2
    assert Activity.objects.filter(user=user).count() == 2


def test_un_fichier_xml_invalide_leve_une_erreur_explicite(user):
    with pytest.raises(ExportParseError):
        parse_export(user, BytesIO(b"ceci n'est pas du xml"))
