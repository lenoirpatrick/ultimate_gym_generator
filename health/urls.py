from django.urls import path

from . import views

app_name = "health"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("import/", views.import_view, name="import"),
    path("cles-api/", views.api_keys, name="api_keys"),
    path("cles-api/<int:pk>/revoquer/", views.api_key_revoke, name="api_key_revoke"),
    path("api/ingestion/", views.ingest, name="ingest"),
]
