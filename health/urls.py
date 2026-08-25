from django.urls import path

from . import views

app_name = "health"

urlpatterns = [
    path("import/", views.import_view, name="import"),
]
