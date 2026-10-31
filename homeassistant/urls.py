from django.urls import path

from . import views

app_name = "homeassistant"

urlpatterns = [
    path("configuration/", views.settings_view, name="settings"),
    path("configuration/test/", views.connection_test, name="test"),
]
