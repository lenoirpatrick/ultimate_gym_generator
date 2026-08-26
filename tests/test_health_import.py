from datetime import date
from io import BytesIO
from pathlib import Path

import pytest

from health.importer import ExportParseError, parse_export
from health.models import Activity, DailySteps, WeightMeasurement

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
    # duration="32.5" durationUnit="min" — coïncide ici avec endDate - startDate.
    assert run.duration_seconds == 1950


def test_une_seance_mise_en_pause_utilise_la_duree_active_pas_l_ecart_horaire(user):
    # Issue #79 : une séance interrompue (feu rouge, calibrage GPS…) dure plus
    # longtemps en horloge murale (ici 24 min, 07:00 → 07:24) que son temps de
    # course réel (attribut `duration`, ici 12 min) — c'est ce dernier que
    # l'app Santé affiche, l'allure doit donc s'appuyer dessus.
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <HealthData>
        <Workout workoutActivityType="HKWorkoutActivityTypeRunning"
                 duration="12" durationUnit="min"
                 totalDistance="2" totalDistanceUnit="km"
                 sourceName="Apple Watch"
                 startDate="2024-02-01 07:00:00 +0100"
                 endDate="2024-02-01 07:24:00 +0100"/>
    </HealthData>
    """
    parse_export(user, BytesIO(xml))
    run = Activity.objects.get(user=user, activity_type=Activity.ActivityType.RUNNING)

    assert run.duration_seconds == 12 * 60
    # 12 min pour 2 km = 6 min/km, pas 12 min/km (durée horloge murale/distance).
    assert run.pace_label == "6:00 /km"


def test_sans_attribut_duration_le_repli_est_l_ecart_horaire(user):
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <HealthData>
        <Workout workoutActivityType="HKWorkoutActivityTypeWalking"
                 sourceName="iPhone"
                 startDate="2024-02-01 07:00:00 +0100"
                 endDate="2024-02-01 07:20:00 +0100"/>
    </HealthData>
    """
    parse_export(user, BytesIO(xml))
    walk = Activity.objects.get(user=user, activity_type=Activity.ActivityType.WALKING)
    assert walk.duration_seconds == 20 * 60


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


def test_since_ecarte_les_enregistrements_anterieurs(user):
    # Fixture : poids le 01/01 et le 08/01, activités le 02/01 et le 03/01,
    # pas le 01/01 (x2) et le 02/01.
    result = parse_export(user, BytesIO(_fixture_bytes()), since=date(2024, 1, 5))

    assert result.weights_created == 1
    assert result.activities_created == 0
    assert result.daily_steps_created == 0
    assert result.skipped_before_since == 6
    assert WeightMeasurement.objects.filter(user=user).count() == 1
    assert Activity.objects.filter(user=user).count() == 0
    assert DailySteps.objects.filter(user=user).count() == 0


def test_since_none_n_ecarte_rien(user):
    result = parse_export(user, BytesIO(_fixture_bytes()), since=None)
    assert result.skipped_before_since == 0


def test_les_pas_sont_agreges_par_jour(user):
    result = parse_export(user, BytesIO(_fixture_bytes()))

    assert result.daily_steps_created == 2
    assert result.daily_steps_updated == 0
    assert DailySteps.objects.get(user=user, date=date(2024, 1, 1)).steps == 2000
    assert DailySteps.objects.get(user=user, date=date(2024, 1, 2)).steps == 3000


def test_reimporter_remplace_le_total_de_pas_sans_le_doubler(user):
    parse_export(user, BytesIO(_fixture_bytes()))
    result = parse_export(user, BytesIO(_fixture_bytes()))

    assert result.daily_steps_created == 0
    assert result.daily_steps_updated == 2
    assert DailySteps.objects.get(user=user, date=date(2024, 1, 1)).steps == 2000
    assert DailySteps.objects.filter(user=user).count() == 2


def test_les_pas_ne_se_doublent_pas_entre_iphone_et_watch(user):
    # Issue #78 : iPhone et Watch rapportent souvent les mêmes pas en double
    # sur des intervalles qui se recouvrent. Le total du jour retenu est le
    # maximum atteint par une seule source, pas la somme des deux.
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <HealthData>
        <Record type="HKQuantityTypeIdentifierStepCount" sourceName="iPhone"
                unit="count" startDate="2024-01-01 08:00:00 +0100"
                endDate="2024-01-01 08:15:00 +0100" value="1000"/>
        <Record type="HKQuantityTypeIdentifierStepCount" sourceName="iPhone"
                unit="count" startDate="2024-01-01 09:00:00 +0100"
                endDate="2024-01-01 09:15:00 +0100" value="500"/>
        <Record type="HKQuantityTypeIdentifierStepCount" sourceName="Watch"
                unit="count" startDate="2024-01-01 08:00:00 +0100"
                endDate="2024-01-01 08:15:00 +0100" value="1000"/>
    </HealthData>
    """
    result = parse_export(user, BytesIO(xml))

    assert result.daily_steps_created == 1
    # iPhone total 1500 (1000 + 500), Watch total 1000 : le jour retenu est
    # 1500, pas 2500 (la somme des deux sources sur l'intervalle commun).
    assert DailySteps.objects.get(user=user, date=date(2024, 1, 1)).steps == 1500
