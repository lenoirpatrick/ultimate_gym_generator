"""Traduction des consignes d'exercices vers le français, par IA (issue #29).

Optionnelle et déclenchée à la demande, jamais au premier amorçage : sans
fournisseur configuré, ou si l'appel échoue, les fiches restent en anglais et
le référentiel reste parfaitement utilisable — voir `exercises.catalog`.
"""

import json
import logging

from aiproviders.clients import ProviderError, get_active_client

logger = logging.getLogger(__name__)

#: Une fiche compte au plus une dizaine de consignes courtes.
MAX_TOKENS = 1500

SYSTEM_PROMPT = (
    "Tu traduis des consignes d'exercices de musculation de l'anglais vers le "
    "français, dans le vocabulaire d'un coach sportif francophone. Traduis "
    "fidèlement, sans ajouter ni omettre d'information. Réponds uniquement avec "
    "un tableau JSON de chaînes de caractères, dans le même ordre et en même "
    "nombre que les consignes fournies — aucun texte hors de ce tableau."
)


def translate_instructions(instructions: list[str]) -> list[str] | None:
    """Traduit une liste de consignes, ou `None` si la traduction est indisponible.

    Un échec (aucun fournisseur, quota, réponse mal formée) est journalisé et
    retourne `None` : l'appelant garde alors les consignes anglaises telles
    quelles, sans jamais bloquer le rechargement du référentiel.
    """
    if not instructions:
        return None

    client = get_active_client()
    if client is None:
        return None

    prompt = json.dumps(instructions, ensure_ascii=False)

    try:
        raw = client.generate(prompt, system=SYSTEM_PROMPT, max_tokens=MAX_TOKENS).strip()
    except ProviderError:
        logger.warning("Traduction des consignes indisponible", exc_info=True)
        return None

    return _parse(_strip_code_fence(raw), expected=len(instructions))


def _strip_code_fence(text: str) -> str:
    """Retire un habillage ```json … ``` que certains modèles ajoutent malgré la consigne."""
    if not text.startswith("```"):
        return text

    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _parse(raw: str, *, expected: int) -> list[str] | None:
    try:
        translated = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Réponse de traduction illisible : %r", raw[:200])
        return None

    valide = (
        isinstance(translated, list)
        and len(translated) == expected
        and all(isinstance(item, str) for item in translated)
    )
    if not valide:
        logger.warning("Réponse de traduction incohérente : %r", raw[:200])
        return None

    return translated
