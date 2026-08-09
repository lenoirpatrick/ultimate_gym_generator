import pytest
from django.contrib.auth import get_user_model

DB_FIXTURES = {"db", "transactional_db", "django_db_reset_sequences"}


@pytest.fixture(autouse=True)
def installation_amorcee(request):
    """Reproduit une installation en service : un compte existe, le catalogue est chargé.

    Sans cela, `FirstRunMiddleware` redirigerait chaque test vers l'étape
    d'amorçage qui manque. Les tests qui portent justement sur ces cas se
    marquent `fresh_install` (aucun compte) ou `empty_catalog` (aucun exercice).
    """
    if "fresh_install" in request.keywords:
        return None

    uses_db = request.node.get_closest_marker("django_db") is not None or bool(
        DB_FIXTURES & set(request.fixturenames)
    )
    if not uses_db:
        return None

    # Force la mise en place de la base avant d'écrire : une fixture autouse
    # s'exécute sinon avant celle dont elle dépend implicitement.
    request.getfixturevalue("db")

    amorce = get_user_model().objects.get_or_create(
        email="amorce@example.test",
        defaults={"is_active": False},
    )[0]

    if "empty_catalog" not in request.keywords:
        from exercises import catalog

        catalog.import_all()

    return amorce


@pytest.fixture
def user(db):
    """Utilisateur ordinaire, sans droit d'administration."""
    return get_user_model().objects.create_user(
        email="coach@example.test",
        password="entrainement-42",
    )


@pytest.fixture
def staff(db):
    return get_user_model().objects.create_user(
        email="patron@example.test",
        password="entrainement-42",
        is_staff=True,
    )


@pytest.fixture
def logged_client(client, user):
    client.force_login(user)
    return client


@pytest.fixture
def staff_client(client, staff):
    client.force_login(staff)
    return client
