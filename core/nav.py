"""Structure du menu principal.

Décrite ici plutôt que dans le gabarit : la barre et le tiroir affichent les
mêmes entrées, et deux listes écrites à la main finiraient par diverger.

Trois groupes par domaine plutôt qu'un partage par fréquence d'usage
(issue #76) : **UGG** (l'entraînement lui-même), **Apple Santé** (données
importées d'Apple Health) et **Compte** (identité, réglages, déconnexion —
« Configuration » y est un sous-groupe, pas un niveau de menu séparé).
Chaque groupe devient un menu déroulant indépendant dans la barre (≥ 40rem) ;
sous 40rem, les trois rejoignent un tiroir unique — un téléphone n'a pas la
largeur pour trois boutons de menu côte à côte.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class NavLink:
    """Entrée de menu, désignée par son nom de vue plutôt que par une adresse.

    `is_logout` bascule le rendu vers un formulaire POST (la déconnexion
    n'est pas une navigation GET) — `view` reste vide dans ce cas, seul le
    libellé compte.
    """

    label: str
    view: str = ""
    staff_only: bool = False
    is_logout: bool = False


@dataclass(frozen=True)
class NavGroup:
    """Entrées rassemblées sous un intitulé, avec un unique niveau de sous-groupe.

    `subgroups` couvre le seul besoin actuel — Configuration sous Compte — et
    se rend comme une section repérée par son propre intitulé, pas comme un
    second menu déroulant imbriqué : inutile de complexifier l'ouverture pour
    un menu qui n'a jamais plus de trois niveaux.
    """

    label: str
    links: tuple[NavLink, ...] = ()
    subgroups: tuple["NavGroup", ...] = ()
    #: Rendues après les sous-groupes — seul cas actuel : Déconnexion, qui doit
    #: rester le dernier mot du menu Compte, après Configuration.
    trailing_links: tuple[NavLink, ...] = ()
    #: Nom d'icône optionnel, lu par `partials/nav_dropdown.html`.
    icon: str = ""

    @property
    def is_empty(self) -> bool:
        return not (self.links or self.subgroups or self.trailing_links)


MENU: tuple[NavGroup, ...] = (
    NavGroup(
        "UGG",
        links=(
            NavLink("Séances", "workouts:list"),
            NavLink("Exercices", "exercises:list"),
            NavLink("Favoris", "exercises:favorites"),
        ),
    ),
    NavGroup(
        "Apple Santé",
        icon="apple-health",
        links=(
            NavLink("Analyse", "health:dashboard"),
            NavLink("Import", "health:import"),
        ),
    ),
    NavGroup(
        "Compte",
        links=(NavLink("Mon compte", "accounts:profile"),),
        subgroups=(
            NavGroup(
                "Configuration",
                links=(
                    NavLink("IA", "aiproviders:list", staff_only=True),
                    NavLink("Référentiel", "exercises:reload", staff_only=True),
                    NavLink("Comptes", "accounts:user_list", staff_only=True),
                ),
            ),
        ),
        trailing_links=(NavLink("Déconnexion", is_logout=True),),
    ),
)


def _filtered(group: NavGroup, is_staff: bool) -> NavGroup | None:
    """Copie de `group` réduite à ce que `is_staff` autorise à voir.

    Un sous-groupe vidé de ses entrées disparaît — un intitulé
    « Configuration » sans rien dessous laisserait croire à un droit manquant
    plutôt qu'à une section sans objet pour ce compte.
    """
    links = tuple(link for link in group.links if is_staff or not link.staff_only)
    subgroups = tuple(
        filtered
        for sub in group.subgroups
        if (filtered := _filtered(sub, is_staff)) is not None and not filtered.is_empty
    )
    filtered_group = NavGroup(
        label=group.label,
        links=links,
        subgroups=subgroups,
        trailing_links=group.trailing_links,
        icon=group.icon,
    )
    return None if filtered_group.is_empty else filtered_group


def menu_for(user) -> list[NavGroup]:
    """Menu complet, réduit aux entrées que `user` a le droit de voir."""
    is_staff = bool(getattr(user, "is_staff", False))
    groups = (_filtered(group, is_staff) for group in MENU)
    return [group for group in groups if group is not None]
