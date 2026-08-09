from django.urls import path

from . import views

app_name = "exercises"

urlpatterns = [
    path("", views.exercise_list, name="list"),
    path("chargement/", views.loading, name="loading"),
    path("chargement/lot/", views.load_batch, name="load_batch"),
]
