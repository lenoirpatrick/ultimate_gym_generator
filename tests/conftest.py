import pytest
from django.contrib.auth import get_user_model


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(
        username="coach",
        email="coach@example.test",
        password="entrainement-42",
    )


@pytest.fixture
def logged_client(client, user):
    client.force_login(user)
    return client
