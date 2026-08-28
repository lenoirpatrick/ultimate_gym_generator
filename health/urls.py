from django.urls import path

from . import views

app_name = "health"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("import/", views.import_view, name="import"),
    path("activites/<int:pk>/supprimer/", views.activity_delete, name="activity_delete"),
    path("activites/<int:pk>/type/", views.activity_edit_type, name="activity_edit_type"),
    path("cles-api/", views.api_keys, name="api_keys"),
    path("cles-api/<int:pk>/revoquer/", views.api_key_revoke, name="api_key_revoke"),
    path("api/ingestion/", views.ingest, name="ingest"),
]
