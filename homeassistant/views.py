"""Home Assistant : configuration de la connexion et des entités (issue #129)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from aiproviders.fields import EncryptionKeyError

from .client import HomeAssistantError, get_client
from .forms import ConnectionForm, EntityFormSet
from .models import MAX_ENTITIES, Connection, Entity

# La connexion vaut pour toute l'installation : réservée au personnel.
staff_required = user_passes_test(lambda user: user.is_staff)


def _encryption_key_missing(request: HttpRequest, exc: EncryptionKeyError) -> HttpResponse:
    """Même page que la configuration IA : le jeton se chiffre avec la même clé."""
    return render(
        request, "aiproviders/encryption_key_missing.html", {"error": str(exc)}, status=503
    )


@login_required
@staff_required
def settings_view(request: HttpRequest) -> HttpResponse:
    """Connexion et entités suivies, enregistrées d'un seul envoi."""
    try:
        connection = Connection.load()
        entities = Entity.objects.all()

        if request.method == "POST":
            form = ConnectionForm(request.POST, instance=connection)
            formset = EntityFormSet(request.POST, queryset=entities)
            if form.is_valid() and formset.is_valid():
                # Savepoint dédié : un chiffrement qui échoue (clé absente) ne
                # doit pas laisser la moitié de l'envoi enregistrée.
                with transaction.atomic():
                    form.save()
                    formset.save()
                messages.success(request, "Configuration Home Assistant enregistrée.")
                return redirect("homeassistant:settings")
        else:
            form = ConnectionForm(instance=connection)
            formset = EntityFormSet(queryset=entities)
    except EncryptionKeyError as exc:
        return _encryption_key_missing(request, exc)

    context = {
        "form": form,
        "formset": formset,
        "connection": connection,
        "max_entities": MAX_ENTITIES,
    }
    return render(request, "homeassistant/settings.html", context)


@login_required
@staff_required
@require_POST
def connection_test(request: HttpRequest) -> HttpResponse:
    """Test de connexion déclenché en HTMX, sur la connexion enregistrée."""
    try:
        client = get_client()
        if client is None:
            result = {"ok": False, "message": "Enregistre d'abord l'adresse et le jeton."}
        else:
            result = {"ok": True, "message": client.ping()}
    except (HomeAssistantError, EncryptionKeyError) as exc:
        result = {"ok": False, "message": str(exc)}

    return render(request, "aiproviders/partials/test_result.html", {"result": result})
