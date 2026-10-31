from django.urls import path

from . import views

app_name = "homeassistant"

urlpatterns = [
    path("entites/<int:pk>/", views.entity_card, name="entity"),
    path("entites/<int:pk>/<slug:service>/", views.entity_action, name="action"),
    path("configuration/", views.settings_view, name="settings"),
    path("configuration/test/", views.connection_test, name="test"),
]
