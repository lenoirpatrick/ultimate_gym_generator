from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views
from .forms import EmailAuthenticationForm

app_name = "accounts"

urlpatterns = [
    # Authentification
    path(
        "connexion/",
        auth_views.LoginView.as_view(
            template_name="accounts/login.html",
            authentication_form=EmailAuthenticationForm,
        ),
        name="login",
    ),
    path("deconnexion/", auth_views.LogoutView.as_view(), name="logout"),
    # Premier démarrage et inscription
    path("bienvenue/", views.first_run, name="first_run"),
    path("inscription/", views.register, name="register"),
    # Profil de l'utilisateur connecté
    path("profil/", views.profile, name="profile"),
    path("profil/materiel/", views.equipment, name="equipment"),
    path(
        "profil/mot-de-passe/",
        auth_views.PasswordChangeView.as_view(
            template_name="accounts/password_change.html",
            success_url=reverse_lazy("accounts:password_change_done"),
        ),
        name="password_change",
    ),
    path(
        "profil/mot-de-passe/ok/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="accounts/password_change_done.html"
        ),
        name="password_change_done",
    ),
    # Gestion des comptes, réservée au personnel
    path("comptes/", views.user_list, name="user_list"),
    path("comptes/nouveau/", views.user_create, name="user_create"),
    path("comptes/<int:pk>/", views.user_update, name="user_update"),
]
