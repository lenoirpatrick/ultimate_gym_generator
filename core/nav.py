"""Structure du menu principal.

Décrite ici plutôt que dans le gabarit : la barre et le tiroir affichent les
mêmes entrées, et deux listes écrites à la main finiraient par diverger.

La séparation tient en une question : est-ce qu'on s'en sert à chaque visite,
ou est-ce qu'on le règle une fois ? Les premières restent en clair, les
secondes passent derrière un menu.
"""

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class NavLink:
    """Entrée de menu, désignée par son nom de vue plutôt que par une adresse."""

    label: str
    view: str
    staff_only: bool = False


@dataclass(frozen=True)
class NavGroup:
    """Entrées rassemblées sous un intitulé."""

    label: str
    links: tuple[NavLink, ...]


#: Entrées quotidiennes : le parcours d'entraînement lui-même.
PRIMARY = NavGroup(
    "Navigation",
    (
        NavLink("Séances", "workouts:list"),
        NavLink("Exercices", "exercises:list"),
        NavLink("Favoris", "exercises:favorites"),
    ),
)

#: Ce qui se configure, groupé par responsabilité.
CONFIG: tuple[NavGroup, ...] = (
    NavGroup(
        "Admin",
        (
            NavLink("IA", "aiproviders:list", staff_only=True),
            NavLink("Comptes", "accounts:user_list", staff_only=True),
            NavLink("Référentiel", "exercises:reload", staff_only=True),
        ),
    ),
    NavGroup("Utilisateur", (NavLink("Compte", "accounts:profile"),)),
)


def config_groups(user) -> list[NavGroup]:
    """Groupes de configuration accessibles à cet utilisateur.

    Un groupe vidé de ses entrées n'est pas rendu : un intitulé « Admin » sans
    rien dessous laisserait croire à un droit manquant plutôt qu'à une section
    sans objet.
    """
    is_staff = bool(getattr(user, "is_staff", False))

    groups = []
    for group in CONFIG:
        links = tuple(link for link in group.links if is_staff or not link.staff_only)
        if links:
            groups.append(replace(group, links=links))
    return groups
