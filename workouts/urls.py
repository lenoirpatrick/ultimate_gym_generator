from django.urls import path

from . import views

app_name = "workouts"

urlpatterns = [
    path("", views.workout_list, name="list"),
    path("nouvelle/", views.workout_create, name="create"),
    path("<int:pk>/", views.workout_detail, name="detail"),
    path("<int:pk>/conseils/", views.workout_coaching, name="coaching"),
    path("<int:pk>/supprimer/", views.workout_delete, name="delete"),
]
