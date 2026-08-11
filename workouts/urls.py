from django.urls import path

from . import views

app_name = "workouts"

urlpatterns = [
    path("", views.workout_list, name="list"),
    path("nouvelle/", views.workout_create, name="create"),
    path("<int:pk>/", views.workout_detail, name="detail"),
    path("<int:pk>/conseils/", views.workout_coaching, name="coaching"),
    path("<int:pk>/renommer/", views.workout_rename, name="rename"),
    path(
        "<int:pk>/exercices/<int:item_pk>/rafraichir/",
        views.workout_exercise_refresh,
        name="exercise_refresh",
    ),
    path(
        "<int:pk>/exercices/<int:item_pk>/repos/",
        views.workout_exercise_rest,
        name="exercise_rest",
    ),
    path("<int:pk>/favori/", views.workout_toggle_favorite, name="toggle_favorite"),
    path("<int:pk>/supprimer/", views.workout_delete, name="delete"),
]
