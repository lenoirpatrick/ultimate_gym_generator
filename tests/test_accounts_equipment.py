"""Matériel de l'utilisateur : charges disponibles, validations, écran de configuration."""

from decimal import Decimal

import pytest
from django.urls import reverse

from accounts.models import UserEquipment

pytestmark = pytest.mark.django_db


def creer(user, **fields) -> UserEquipment:
    return UserEquipment.objects.create(user=user, **fields)


# --------------------------------------------------------------------------- #
# Charges disponibles
# --------------------------------------------------------------------------- #


def test_un_jeu_fige_rend_ses_charges_triees(user):
    item = creer(user, equipment="kettlebells", mode="fixed", weights=[16, 8, 24, 12])

    assert item.available_loads() == [Decimal("8"), Decimal("12"), Decimal("16"), Decimal("24")]


def test_une_charge_reglable_enumere_ses_crans(user):
    """Les haltères à poids variables sont explicitement visés par l'issue."""
    item = creer(
        user,
        equipment="dumbbell",
        mode="adjustable",
        min_kg=Decimal("2"),
        max_kg=Decimal("10"),
        step_kg=Decimal("2"),
    )

    assert item.available_loads() == [Decimal(w) for w in (2, 4, 6, 8, 10)]


def test_un_cran_qui_depasserait_le_maximum_est_ecarte(user):
    item = creer(
        user,
        equipment="barbell",
        mode="adjustable",
        min_kg=Decimal("20"),
        max_kg=Decimal("25"),
        step_kg=Decimal("2.5"),
    )

    assert item.available_loads() == [Decimal("20"), Decimal("22.5"), Decimal("25")]


def test_un_materiel_sans_charge_n_en_propose_aucune(user):
    item = creer(user, equipment="body only", mode="bodyweight")

    assert item.available_loads() == []


def test_une_plage_incomplete_ne_produit_aucune_charge(user):
    """Mieux vaut aucune charge qu'une charge inventée à partir de données partielles."""
    item = creer(user, equipment="dumbbell", mode="adjustable", min_kg=Decimal("2"))

    assert item.available_loads() == []


def test_une_plage_immense_reste_bornee(user):
    """Un pas minuscule sur une grande plage ne doit pas produire des milliers de crans."""
    item = creer(
        user,
        equipment="barbell",
        mode="adjustable",
        min_kg=Decimal("1"),
        max_kg=Decimal("500"),
        step_kg=Decimal("0.5"),
    )

    assert len(item.available_loads()) == 200


def test_un_materiel_n_est_declare_qu_une_fois(user):
    creer(user, equipment="dumbbell", mode="bodyweight")

    with pytest.raises(Exception):  # noqa: B017 - IntegrityError selon le moteur
        creer(user, equipment="dumbbell", mode="bodyweight")


# --------------------------------------------------------------------------- #
# Écran de configuration
# --------------------------------------------------------------------------- #


def test_l_ecran_exige_une_authentification(client):
    response = client.get(reverse("accounts:equipment"))

    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


def payload(**overrides) -> dict:
    data = {
        "form-TOTAL_FORMS": "1",
        "form-INITIAL_FORMS": "0",
        "form-MIN_NUM_FORMS": "0",
        "form-MAX_NUM_FORMS": "1000",
        "form-0-equipment": "dumbbell",
        "form-0-mode": "adjustable",
        "form-0-weights": "",
        "form-0-min_kg": "2",
        "form-0-max_kg": "24",
        "form-0-step_kg": "2",
    }
    return data | overrides


def test_une_charge_reglable_s_enregistre(logged_client, user):
    response = logged_client.post(reverse("accounts:equipment"), payload())

    assert response.status_code == 302
    item = UserEquipment.objects.get(user=user, equipment="dumbbell")
    assert item.available_loads()[-1] == Decimal("24")


def test_les_charges_figees_se_saisissent_en_texte(logged_client, user):
    """Écrire « 8, 12, 16 » vaut mieux que d'exiger un tableau JSON."""
    logged_client.post(
        reverse("accounts:equipment"),
        payload(
            **{
                "form-0-equipment": "kettlebells",
                "form-0-mode": "fixed",
                "form-0-weights": "16, 8; 12",
                "form-0-min_kg": "",
                "form-0-max_kg": "",
                "form-0-step_kg": "",
            }
        ),
    )

    item = UserEquipment.objects.get(user=user, equipment="kettlebells")
    assert item.available_loads() == [Decimal("8"), Decimal("12"), Decimal("16")]


def test_une_charge_illisible_est_refusee(logged_client, user):
    response = logged_client.post(
        reverse("accounts:equipment"),
        payload(**{"form-0-mode": "fixed", "form-0-weights": "8, beaucoup"}),
    )

    assert response.status_code == 200
    assert "n&#x27;est pas un poids" in response.content.decode()
    assert not UserEquipment.objects.filter(user=user).exists()


def test_un_jeu_fige_sans_charge_est_refuse(logged_client, user):
    response = logged_client.post(
        reverse("accounts:equipment"),
        payload(**{"form-0-mode": "fixed", "form-0-weights": ""}),
    )

    assert response.status_code == 200
    assert "au moins une charge" in response.content.decode()
    assert not UserEquipment.objects.filter(user=user).exists()


def test_une_plage_inversee_est_refusee(logged_client, user):
    response = logged_client.post(
        reverse("accounts:equipment"),
        payload(**{"form-0-min_kg": "30", "form-0-max_kg": "10"}),
    )

    assert response.status_code == 200
    assert "doit dépasser le minimum" in response.content.decode()
    assert not UserEquipment.objects.filter(user=user).exists()


def test_un_pas_nul_est_refuse(logged_client, user):
    response = logged_client.post(
        reverse("accounts:equipment"),
        payload(**{"form-0-step_kg": "0"}),
    )

    assert response.status_code == 200
    assert "supérieur à zéro" in response.content.decode()


def test_une_plage_incomplete_est_refusee(logged_client, user):
    response = logged_client.post(
        reverse("accounts:equipment"),
        payload(**{"form-0-max_kg": "", "form-0-step_kg": ""}),
    )

    assert response.status_code == 200
    assert "un minimum, un maximum et un pas" in response.content.decode()


def test_le_materiel_d_un_autre_utilisateur_reste_invisible(logged_client, staff_client, staff):
    creer(staff, equipment="cable", mode="bodyweight")

    content = logged_client.get(reverse("accounts:equipment")).content.decode()

    assert content.count('name="form-0-equipment"') == 1
    assert 'value="cable" selected' not in content


def test_un_materiel_se_retire_dynamiquement(logged_client, user):
    """Un clic sur le bouton suffit — pas de case à cocher ni de réenregistrement
    de tout le formulaire (issue #41)."""
    item = creer(user, equipment="bands", mode="bodyweight")

    response = logged_client.post(reverse("accounts:equipment_delete", args=[item.pk]))

    assert response.status_code == 200
    assert not UserEquipment.objects.filter(user=user).exists()


def test_la_suppression_dynamique_exige_une_authentification(client, user):
    item = creer(user, equipment="bands", mode="bodyweight")

    response = client.post(reverse("accounts:equipment_delete", args=[item.pk]))

    assert response.status_code == 302
    assert reverse("accounts:login") in response.url
    assert UserEquipment.objects.filter(pk=item.pk).exists()


def test_la_suppression_dynamique_exige_un_post(logged_client, user):
    item = creer(user, equipment="bands", mode="bodyweight")

    response = logged_client.get(reverse("accounts:equipment_delete", args=[item.pk]))

    assert response.status_code == 405
    assert UserEquipment.objects.filter(pk=item.pk).exists()


def test_la_suppression_dynamique_ignore_le_materiel_d_un_autre_utilisateur(logged_client, staff):
    item = creer(staff, equipment="cable", mode="bodyweight")

    response = logged_client.post(reverse("accounts:equipment_delete", args=[item.pk]))

    assert response.status_code == 404
    assert UserEquipment.objects.filter(pk=item.pk).exists()


def test_la_suppression_d_une_ligne_du_milieu_renumerote_les_suivantes(logged_client, user):
    """Les lignes restantes doivent rester des indices contigus (`form-0`, `form-1`,
    …) : un trou laissé par la ligne retirée casserait le réenregistrement complet
    qui suit, `TOTAL_FORMS` ne correspondant plus aux lignes réellement présentes."""
    first = creer(user, equipment="bands", mode="bodyweight")
    second = creer(user, equipment="cable", mode="bodyweight")

    response = logged_client.post(reverse("accounts:equipment_delete", args=[first.pk]))
    content = response.content.decode()

    assert 'name="form-TOTAL_FORMS" value="2"' in content  # ligne restante + ligne vide
    assert f'value="{second.pk}"' in content
    assert 'name="form-0-equipment"' in content
    assert 'name="form-1-equipment"' in content
    assert 'name="form-2-equipment"' not in content


def test_le_profil_mene_au_materiel(logged_client):
    content = logged_client.get(reverse("accounts:profile")).content.decode()

    assert reverse("accounts:equipment") in content


# --------------------------------------------------------------------------- #
# Mode conditionnel et icônes (issue #37)
# --------------------------------------------------------------------------- #


def test_le_mode_se_choisit_par_puces_pas_par_menu_deroulant(logged_client):
    """Un `<select>` n'aurait pas permis la bascule CSS pure des champs de charge."""
    content = logged_client.get(reverse("accounts:equipment")).content.decode()

    assert '<select name="form-0-mode"' not in content
    assert 'name="form-0-mode" value="fixed"' in content
    assert 'name="form-0-mode" value="adjustable"' in content
    assert 'name="form-0-mode" value="bodyweight"' in content


def test_chaque_ligne_scope_ses_bascules_css(logged_client, user):
    """`.ugg-equipment-row` doit envelopper le mode et les deux groupes de champs
    pour que `:has()` puisse ne révéler que celui qui correspond (issue #37)."""
    creer(user, equipment="dumbbell", mode="adjustable", min_kg=2, max_kg=10, step_kg=2)

    content = logged_client.get(reverse("accounts:equipment")).content.decode()

    assert content.count("ugg-equipment-row") >= 2  # ligne existante + ligne vide
    assert "ugg-equipment__weights" in content
    assert "ugg-equipment__range" in content


def test_une_icone_existe_pour_chaque_materiel_du_referentiel(logged_client):
    from django.template.defaultfilters import slugify

    from exercises.models import Exercise

    content = logged_client.get(reverse("accounts:equipment")).content.decode()

    for value, _label in Exercise.Equipment.choices:
        assert f"ugg-equipment__icon--{slugify(value)}" in content


def test_les_deux_groupes_de_charge_restent_postables(logged_client, user):
    """La bascule CSS ne modifie pas ce qui est validé côté serveur : les deux
    groupes de champs restent dans le formulaire, seul leur affichage change."""
    creer(user, equipment="kettlebells", mode="fixed", weights=[8, 12, 16])

    content = logged_client.get(reverse("accounts:equipment")).content.decode()

    assert 'name="form-0-weights"' in content
    assert 'name="form-0-min_kg"' in content


# --------------------------------------------------------------------------- #
# Réenregistrement d'une ligne sans charges figées
# --------------------------------------------------------------------------- #
#
# `weights` est à la fois un champ du modèle (liste JSON) et un champ de
# formulaire déclaré (texte) : `ModelForm.__init__` peuple `self.initial`
# avec la liste brute du modèle avant que `EquipmentForm.__init__` ne la
# retraduise en texte — une liste vide laissait passer telle quelle, affichée
# comme le texte littéral « [] ». Reposter cette valeur sans y toucher
# échouait alors la validation (« "[]" n'est pas un poids »), empêchant tout
# réenregistrement d'une ligne existante — le symptôme signalé.


def test_une_liste_de_charges_vide_ne_s_affiche_pas_comme_des_crochets(user):
    from accounts.forms import EquipmentForm

    item = creer(user, equipment="dumbbell", mode="adjustable", min_kg=2, max_kg=24, step_kg=2)

    assert EquipmentForm(instance=item).initial["weights"] == ""


def test_reenregistrer_une_ligne_reglable_sans_y_toucher_reussit(logged_client, user):
    """Poste la valeur telle que `EquipmentForm` la propose réellement au rendu —
    un payload « form-0-weights »: "" écrit à la main n'aurait pas rejoué le bug,
    dont l'origine est précisément ce que le formulaire place dans `initial`."""
    from accounts.forms import EquipmentForm

    item = creer(user, equipment="dumbbell", mode="adjustable", min_kg=2, max_kg=24, step_kg=2)
    weights_as_rendered = str(EquipmentForm(instance=item).initial["weights"])

    response = logged_client.post(
        reverse("accounts:equipment"),
        payload(
            **{
                "form-TOTAL_FORMS": "1",
                "form-INITIAL_FORMS": "1",
                "form-0-id": str(item.pk),
                "form-0-equipment": "dumbbell",
                "form-0-mode": "adjustable",
                "form-0-weights": weights_as_rendered,
                "form-0-min_kg": "2",
                "form-0-max_kg": "24",
                "form-0-step_kg": "2",
            }
        ),
    )

    assert response.status_code == 302
    item.refresh_from_db()
    assert item.min_kg == Decimal("2")
