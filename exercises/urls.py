from django.urls import path

from . import views

app_name = "exercises"

urlpatterns = [
    path("chargement/", views.loading, name="loading"),
    path("chargement/lot/", views.load_batch, name="load_batch"),
]
