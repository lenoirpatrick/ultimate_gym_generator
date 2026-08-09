from django.urls import path

from . import views

app_name = "aiproviders"

urlpatterns = [
    path("", views.credential_list, name="list"),
    path("<slug:provider>/", views.credential_edit, name="edit"),
    path("<slug:provider>/test/", views.credential_test, name="test"),
]
