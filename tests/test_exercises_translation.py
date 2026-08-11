"""Traduction IA des consignes d'exercices : habillage optionnel (issue #29)."""

from aiproviders.clients import ProviderError
from exercises import translation

INSTRUCTIONS = ["Lie down.", "Stand up."]


def stub_client(monkeypatch, generate):
    monkeypatch.setattr(
        "exercises.translation.get_active_client",
        lambda: type("Stub", (), {"generate": generate})(),
    )


def test_sans_fournisseur_la_traduction_est_ignoree(monkeypatch):
    monkeypatch.setattr("exercises.translation.get_active_client", lambda: None)

    assert translation.translate_instructions(INSTRUCTIONS) is None


def test_une_liste_vide_n_appelle_pas_le_fournisseur(monkeypatch):
    def refuser(self, prompt, **kwargs):
        raise AssertionError("le fournisseur ne doit pas être appelé")

    stub_client(monkeypatch, refuser)

    assert translation.translate_instructions([]) is None


def test_la_traduction_est_analysee(monkeypatch):
    stub_client(monkeypatch, lambda self, prompt, **kwargs: '["Allonge-toi.", "Lève-toi."]')

    assert translation.translate_instructions(INSTRUCTIONS) == ["Allonge-toi.", "Lève-toi."]


def test_les_consignes_sont_envoyees_au_fournisseur(monkeypatch):
    captured = {}

    def capturer(self, prompt, **kwargs):
        captured["prompt"] = prompt
        return '["Allonge-toi.", "Lève-toi."]'

    stub_client(monkeypatch, capturer)
    translation.translate_instructions(INSTRUCTIONS)

    assert "Lie down." in captured["prompt"]
    assert "Stand up." in captured["prompt"]


def test_un_habillage_de_bloc_de_code_est_retire(monkeypatch):
    """Certains modèles enrobent leur réponse malgré la consigne — tolérable, pas bloquant."""
    reponse = '```json\n["Allonge-toi.", "Lève-toi."]\n```'
    stub_client(monkeypatch, lambda self, prompt, **kwargs: reponse)

    assert translation.translate_instructions(INSTRUCTIONS) == ["Allonge-toi.", "Lève-toi."]


def test_une_reponse_illisible_est_ignoree(monkeypatch):
    stub_client(monkeypatch, lambda self, prompt, **kwargs: "pas du json")

    assert translation.translate_instructions(INSTRUCTIONS) is None


def test_une_reponse_de_longueur_differente_est_ignoree(monkeypatch):
    """Une consigne perdue ou ajoutée par le modèle ne doit pas être acceptée telle quelle."""
    stub_client(monkeypatch, lambda self, prompt, **kwargs: '["Une seule ligne."]')

    assert translation.translate_instructions(INSTRUCTIONS) is None


def test_une_reponse_qui_n_est_pas_une_liste_de_chaines_est_ignoree(monkeypatch):
    stub_client(monkeypatch, lambda self, prompt, **kwargs: '["Allonge-toi.", 2]')

    assert translation.translate_instructions(INSTRUCTIONS) is None


def test_une_panne_du_fournisseur_ne_remonte_pas(monkeypatch):
    def tomber(self, prompt, **kwargs):
        raise ProviderError("Quota dépassé.")

    stub_client(monkeypatch, tomber)

    assert translation.translate_instructions(INSTRUCTIONS) is None


def test_le_budget_de_jetons_reste_genereux():
    """Les modèles à raisonnement étendu (Gemini 2.5+/3.x, entre autres)
    consomment une partie du budget en jetons de réflexion invisibles avant
    la réponse visible — une limite trop basse tronque le JSON en plein
    milieu (issue #29 suite). Garde-fou contre une régression silencieuse."""
    assert translation.MAX_TOKENS >= 4000
