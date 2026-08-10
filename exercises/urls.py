from django.urls import path

from . import views

app_name = "exercises"

urlpatterns = [
    path("", views.exercise_list, name="list"),
    path("favoris/", views.favorite_list, name="favorites"),
    path("<int:pk>/favori/", views.toggle_favorite, name="toggle_favorite"),
    path("<int:pk>/traduire/", views.translate_exercise, name="translate"),
    path("chargement/", views.loading, name="loading"),
    path("chargement/lot/", views.load_batch, name="load_batch"),
    path("recharger/", views.reload_catalog, name="reload"),
    path("recharger/lot/", views.reload_batch, name="reload_batch"),
]
