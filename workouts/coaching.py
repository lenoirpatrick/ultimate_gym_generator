"""Conseils rédigés par l'IA pour une séance déjà composée.

L'IA n'intervient qu'en habillage : la séance est complète et juste avant
qu'elle ne soit appelée. Une clé absente, un quota dépassé ou une réponse vide
laissent donc l'écran parfaitement utilisable — c'est le texte qui manque, pas
l'entraînement.
"""

import logging

from aiproviders.clients import ProviderError, get_active_client

from .models import Workout

logger = logging.getLogger(__name__)

#: Assez pour quelques paragraphes, pas assez pour une dissertation.
MAX_TOKENS = 700

SYSTEM_PROMPT = (
    "Tu es un coach sportif expérimenté. Tu réponds en français, sur un ton direct "
    "et tutoyant, sans emphase ni superlatif. Tu ne réécris pas la séance et tu ne "
    "proposes pas d'autres exercices : elle est déjà fixée. Tu donnes uniquement "
    "des conseils d'exécution et de sécurité, en trois courts paragraphes au plus, "
    "sans titre ni liste à puces."
)


def describe(workout: Workout) -> str:
    """Résumé de la séance envoyé au fournisseur."""
    muscles = ", ".join(muscle.name for muscle in workout.muscles.all()) or "tout le corps"

    lines = [
        f"Format : {workout.get_format_display()}",
        f"Durée : {workout.planned_minutes} minutes",
        f"Parties du corps : {muscles}",
        "Déroulé :",
    ]

    for item in workout.items.all():
        if item.is_timed:
            prescription = f"{item.work_seconds}s d'effort / {item.rest_seconds}s de repos"
            prescription += f", {item.rounds} fois"
        else:
            prescription = f"séries de {', '.join(str(rep) for rep in item.reps)} répétitions"

        charge = f" à {item.load_summary}" if item.load_summary else ""
        lines.append(f"- {item.exercise.name} : {prescription}{charge}")

    return "\n".join(lines)


def _generate(workout: Workout) -> str | None:
    """Appelle le fournisseur actif pour de nouveaux conseils, ou `None` s'il n'y
    en a pas d'utilisable — absent, en échec, ou réponse vide."""
    client = get_active_client()
    if client is None:
        return None

    prompt = (
        "Voici la séance que je vais faire. Donne-moi tes conseils d'exécution.\n\n"
        f"{describe(workout)}"
    )

    try:
        notes = client.generate(prompt, system=SYSTEM_PROMPT, max_tokens=MAX_TOKENS).strip()
    except ProviderError:
        logger.warning("Conseils de séance indisponibles", exc_info=True)
        return None

    return notes or None


def write_notes(workout: Workout) -> str:
    """Rédige et enregistre les conseils une première fois. Retourne une chaîne
    vide en cas d'échec ou si aucun fournisseur n'est configuré.

    Les erreurs sont journalisées, pas remontées : l'utilisateur n'a rien à faire
    d'un message d'erreur de fournisseur devant une séance qui, elle, est prête.
    """
    if workout.coaching_notes:
        return workout.coaching_notes

    notes = _generate(workout)
    if notes is None:
        return ""

    workout.coaching_notes = notes
    workout.save(update_fields=["coaching_notes"])
    return notes


def refresh_notes(workout: Workout) -> str | None:
    """Régénère les conseils à la demande, quels que soient ceux déjà enregistrés.

    Contrairement à `write_notes`, un rafraîchissement est une action
    volontaire : son échec (`None`) doit rester visible plutôt que de
    disparaître en silence — même principe que
    `exercises.views.translate_exercise`. Les conseils déjà enregistrés ne
    sont jamais effacés par un échec, seul un succès les remplace.
    """
    notes = _generate(workout)
    if notes is None:
        return None

    workout.coaching_notes = notes
    workout.save(update_fields=["coaching_notes"])
    return notes
