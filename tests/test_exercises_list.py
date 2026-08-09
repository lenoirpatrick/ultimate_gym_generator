"""Catalogue filtrable : sémantique des filtres, rendu des cartes, pagination."""

import re

import pytest
from django.http import QueryDict
from django.urls import reverse

from exercises import filters, views

pytestmark = pytest.mark.django_db

# Source de test — voir tests/fixtures/exercises.json :
#   Barbell_Squat        débutant     · barre    · poussée · quadriceps (+ fessiers, ischio)
#   Calf_Stretch         débutant     · —        · —       · mollets
#   Dumbbell_Bench_Press intermédiaire· haltères · poussée · pectoraux (+ épaules, triceps)
#   Text_Only_Exercise   confirmé     · —        · —       · —
TOTAL = 4
URL = "/exercices/"


def noms(response) -> list[str]:
    """Noms des exercices rendus, dans l'ordre d'affichage."""
    return re.findall(r'<h3 class="ugg-title text-base">([^<]+)</h3>', response.content.decode())


# --------------------------------------------------------------------------- #
# Accès
# --------------------------------------------------------------------------- #


def test_le_catalogue_exige_une_authentification(client):
    response = client.get(reverse("exercises:list"))

    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


def test_le_catalogue_est_ouvert_a_tout_utilisateur(logged_client):
    """Consulter les exercices ne demande aucun droit particulier."""
    assert logged_client.get(reverse("exercises:list")).status_code == 200


# --------------------------------------------------------------------------- #
# Affichage
# --------------------------------------------------------------------------- #


def test_tous_les_exercices_sont_listes_sans_filtre(logged_client):
    response = logged_client.get(reverse("exercises:list"))

    assert len(noms(response)) == TOTAL


def test_une_carte_presente_les_caracteristiques_traduites(logged_client):
    content = logged_client.get(reverse("exercises:list")).content.decode()

    assert "Barbell Squat" in content
    assert "Renforcement" in content
    assert "Débutant" in content
    assert "Barre" in content
    assert "Polyarticulaire" in content


def test_une_carte_distingue_muscles_principaux_et_secondaires(logged_client):
    content = logged_client.get(reverse("exercises:list")).content.decode()

    assert "Quadriceps" in content
    assert "Fessiers" in content
    assert "Principal" in content
    assert "Secondaire" in content


def test_les_consignes_sont_repliees_dans_la_carte(logged_client):
    """Déroulées, elles noieraient la grille."""
    content = logged_client.get(reverse("exercises:list")).content.decode()

    assert "Comment l'exécuter" in content
    assert "Placer la barre sur les trapèzes" in content


def test_les_quatre_criteres_sont_proposes(logged_client):
    content = logged_client.get(reverse("exercises:list")).content.decode()

    for legende in ("Niveau", "Type d&#x27;effort", "Matériel", "Muscle travaillé"):
        assert legende in content


def test_les_options_de_filtre_sont_des_cases_a_cocher(logged_client):
    """Un select multiple serait impraticable au pouce (CLAUDE.md § Filtres)."""
    content = logged_client.get(reverse("exercises:list")).content.decode()

    assert 'type="checkbox"' in content
    assert "<select" not in content


# --------------------------------------------------------------------------- #
# Sémantique du filtrage
# --------------------------------------------------------------------------- #


def test_un_critere_restreint_la_liste(logged_client):
    response = logged_client.get(URL, {"materiel": "barbell"})

    assert noms(response) == ["Barbell Squat"]


def test_deux_valeurs_d_un_meme_critere_s_additionnent(logged_client):
    response = logged_client.get(URL, {"materiel": ["barbell", "dumbbell"]})

    assert noms(response) == ["Barbell Squat", "Dumbbell Bench Press"]


def test_deux_criteres_differents_se_cumulent(logged_client):
    """Débutant ET à la barre : le développé couché, intermédiaire, doit sortir."""
    response = logged_client.get(URL, {"niveau": "beginner", "materiel": ["barbell", "dumbbell"]})

    assert noms(response) == ["Barbell Squat"]


def test_le_filtre_par_muscle_couvre_les_deux_roles(logged_client):
    """Un exercice qui sollicite les fessiers en second reste un exercice pour les fessiers."""
    response = logged_client.get(URL, {"muscle": "glutes"})

    assert noms(response) == ["Barbell Squat"]


def test_le_filtre_par_muscle_ne_duplique_pas_les_cartes(logged_client):
    """Deux muscles d'un même exercice multiplieraient les lignes sans `distinct`."""
    response = logged_client.get(URL, {"muscle": ["quadriceps", "glutes", "hamstrings"]})

    assert noms(response) == ["Barbell Squat"]


def test_le_filtre_par_niveau_et_par_effort(logged_client):
    response = logged_client.get(URL, {"effort": "push", "niveau": "intermediate"})

    assert noms(response) == ["Dumbbell Bench Press"]


def test_une_valeur_inconnue_est_ignoree(logged_client):
    """Un lien partagé ne doit pas casser parce que le référentiel a changé."""
    response = logged_client.get(URL, {"materiel": "jetpack"})

    assert len(noms(response)) == TOTAL


def test_un_critere_inconnu_est_ignore(logged_client):
    response = logged_client.get(URL, {"couleur": "rouge"})

    assert response.status_code == 200
    assert len(noms(response)) == TOTAL


# --------------------------------------------------------------------------- #
# États du filtre
# --------------------------------------------------------------------------- #


def test_les_cases_cochees_sont_conservees_a_l_affichage(logged_client):
    """Sans cela, l'utilisateur perdrait sa sélection à chaque rechargement."""
    content = logged_client.get(URL, {"materiel": "barbell"}).content.decode()

    assert 'value="barbell"\n                       checked' in content.replace("\r", "")


def test_un_critere_actif_affiche_son_nombre_de_selections(logged_client):
    content = logged_client.get(URL, {"materiel": ["barbell", "dumbbell"]}).content.decode()

    assert 'class="ugg-filter__badge">2<' in content


def test_le_compteur_suit_un_filtrage_sans_rechargement(logged_client):
    """Le formulaire n'est pas re-rendu : sans échange hors-bande, le compteur mentirait."""
    content = logged_client.get(
        URL, {"materiel": "barbell"}, headers={"HX-Request": "true"}
    ).content.decode()

    assert 'id="badge-materiel" hx-swap-oob="true"' in content
    assert 'class="ugg-filter__badge">1<' in content


def test_les_compteurs_ne_sont_pas_dupliques_au_premier_rendu(logged_client):
    """Hors HTMX, les compteurs sont déjà dans le formulaire : les répéter les dédoublerait."""
    content = logged_client.get(URL, {"materiel": "barbell"}).content.decode()

    assert "hx-swap-oob" not in content
    assert content.count('id="badge-materiel"') == 1


def test_un_critere_actif_est_deplie(logged_client):
    content = logged_client.get(URL, {"materiel": "barbell"}).content.decode()

    assert '<details class="ugg-filter" open>' in content


def test_une_recherche_sans_resultat_propose_de_reprendre(logged_client):
    response = logged_client.get(URL, {"materiel": "barbell", "muscle": "chest"})

    content = response.content.decode()
    assert noms(response) == []
    assert "Aucun exercice ne correspond" in content
    assert "Tout effacer" in content


def test_sans_filtre_aucune_invitation_a_effacer(logged_client):
    content = logged_client.get(reverse("exercises:list")).content.decode()

    assert "Tout effacer" not in content


# --------------------------------------------------------------------------- #
# Rendu partiel et adresse
# --------------------------------------------------------------------------- #


def test_une_requete_htmx_ne_rend_que_les_resultats(logged_client):
    content = logged_client.get(URL, headers={"HX-Request": "true"}).content.decode()

    assert "Barbell Squat" in content
    # Ni gabarit de base, ni formulaire de filtres : seul le bloc de résultats.
    assert "<!DOCTYPE html>" not in content
    assert 'type="checkbox"' not in content


def test_le_formulaire_reecrit_l_adresse(logged_client):
    """Une sélection doit se partager et survivre à un rechargement."""
    content = logged_client.get(reverse("exercises:list")).content.decode()

    assert 'hx-push-url="true"' in content
    assert 'hx-target="#resultats"' in content


def test_la_zone_de_resultats_est_annoncee(logged_client):
    content = logged_client.get(reverse("exercises:list")).content.decode()

    assert 'aria-live="polite"' in content


# --------------------------------------------------------------------------- #
# Pagination
# --------------------------------------------------------------------------- #


def test_une_seule_page_n_affiche_pas_de_pagination(logged_client):
    content = logged_client.get(reverse("exercises:list")).content.decode()

    assert "Pagination des exercices" not in content


def test_la_pagination_apparait_au_dela_d_une_page(logged_client, monkeypatch):
    monkeypatch.setattr(views, "PAGE_SIZE", 2)

    content = logged_client.get(reverse("exercises:list")).content.decode()

    assert "Pagination des exercices" in content
    assert "Page 1 sur 2" in content


def test_la_pagination_conserve_les_criteres(logged_client, monkeypatch):
    """Changer de page ne doit pas réinitialiser la recherche."""
    monkeypatch.setattr(views, "PAGE_SIZE", 1)

    content = logged_client.get(URL, {"niveau": "beginner"}).content.decode()

    assert "?niveau=beginner&page=2" in content


def test_une_page_hors_bornes_retombe_sur_la_derniere(logged_client, monkeypatch):
    monkeypatch.setattr(views, "PAGE_SIZE", 2)

    content = logged_client.get(URL, {"page": "99"}).content.decode()

    assert "Page 2 sur 2" in content


def test_un_numero_de_page_illisible_ne_casse_pas_la_liste(logged_client):
    response = logged_client.get(URL, {"page": "n'importe quoi"})

    assert response.status_code == 200
    assert len(noms(response)) == TOTAL


# --------------------------------------------------------------------------- #
# Efficacité
# --------------------------------------------------------------------------- #


def test_les_muscles_sont_precharges(django_assert_num_queries, user):
    """Sans préchargement, chaque carte ajouterait deux requêtes au rendu de la grille."""
    exercises = list(filters.filter_exercises(QueryDict(), user))
    assert len(exercises) == TOTAL

    with django_assert_num_queries(0):
        for exercise in exercises:
            list(exercise.primary_muscles.all())
            list(exercise.secondary_muscles.all())
