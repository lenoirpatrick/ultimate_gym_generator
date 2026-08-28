"""Filtrage par panneau repliable, partagé entre les domaines qui en ont besoin.

Extrait d'`exercises.filters` au moment où `health` en a eu besoin à son tour
(#73) : deux usages valent une abstraction, un seul ne la justifiait pas.
Sémantique constante partout où c'est utilisé : plusieurs valeurs d'un même
critère s'additionnent (OU), deux critères se cumulent (ET).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Option:
    """Valeur cochable d'un critère."""

    value: str
    label: str
    selected: bool


@dataclass(frozen=True)
class FilterGroup:
    """Critère de filtrage et l'état de ses options."""

    #: Nom du paramètre de requête, en français comme le reste des URL.
    name: str
    legend: str
    options: list[Option]

    @property
    def selected_count(self) -> int:
        return sum(1 for option in self.options if option.selected)


def selected_values(params, name: str, allowed: set[str]) -> list[str]:
    """Valeurs cochées pour un critère, réduites à celles qui existent.

    Une valeur inconnue est ignorée plutôt que refusée — un lien partagé ne
    doit pas casser parce que le référentiel a changé depuis.
    """
    return [value for value in params.getlist(name) if value in allowed]
