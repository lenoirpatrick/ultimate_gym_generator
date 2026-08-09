"""Modèle utilisateur : mesures corporelles et affichage."""

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from accounts.models import User


@pytest.mark.django_db
def test_l_imc_est_calcule_a_partir_de_la_taille_et_du_poids():
    athlete = User(height_cm=180, weight_kg=Decimal("81.0"))

    assert athlete.bmi == Decimal("25.0")


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("height", "weight"),
    [(None, Decimal("80.0")), (180, None), (None, None)],
)
def test_l_imc_est_absent_tant_qu_une_mesure_manque(height, weight):
    athlete = User(height_cm=height, weight_kg=weight)

    assert athlete.bmi is None
    assert athlete.has_body_metrics is False


@pytest.mark.django_db
@pytest.mark.parametrize("height", [10, 300])
def test_une_taille_hors_bornes_est_refusee(height):
    athlete = User(username="a", email="a@example.test", height_cm=height)

    with pytest.raises(ValidationError) as excinfo:
        athlete.full_clean()

    assert "height_cm" in excinfo.value.error_dict


@pytest.mark.django_db
@pytest.mark.parametrize("weight", [Decimal("5.0"), Decimal("400.0")])
def test_un_poids_hors_bornes_est_refuse(weight):
    athlete = User(username="a", email="a@example.test", weight_kg=weight)

    with pytest.raises(ValidationError) as excinfo:
        athlete.full_clean()

    assert "weight_kg" in excinfo.value.error_dict


@pytest.mark.django_db
def test_les_initiales_viennent_du_nom_complet():
    assert User(first_name="Alex", last_name="Martin").initials == "AM"


@pytest.mark.django_db
def test_les_initiales_retombent_sur_le_nom_d_utilisateur():
    assert User(username="coach").initials == "CO"


@pytest.mark.django_db
def test_le_sexe_par_defaut_ne_se_prononce_pas():
    athlete = User.objects.create_user(username="neutre", email="n@example.test")

    assert athlete.gender == User.Gender.UNDISCLOSED


@pytest.mark.django_db
def test_l_adresse_e_mail_est_unique():
    User.objects.create_user(username="premier", email="doublon@example.test")

    with pytest.raises(Exception):  # noqa: B017 - IntegrityError selon le moteur
        User.objects.create_user(username="second", email="doublon@example.test")
