"""Configuration des credentials d'IA générative."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .clients import ProviderError, get_client
from .forms import ProviderCredentialForm
from .models import ProviderCredential
from .registry import PROVIDERS, get_spec

# Les credentials d'IA valent pour toute l'installation, pas pour un utilisateur :
# leur configuration est réservée au personnel.
staff_required = user_passes_test(lambda user: user.is_staff)


def _spec_or_404(slug: str):
    try:
        return get_spec(slug)
    except KeyError as exc:
        raise Http404(f"Fournisseur inconnu : {slug}") from exc


@login_required
@staff_required
def credential_list(request: HttpRequest) -> HttpResponse:
    """Une ligne par fournisseur du registre, configurée ou non."""
    stored = {c.provider: c for c in ProviderCredential.objects.all()}
    rows = [{"spec": spec, "credential": stored.get(spec.slug)} for spec in PROVIDERS]
    return render(request, "aiproviders/credential_list.html", {"rows": rows})


@login_required
@staff_required
def credential_edit(request: HttpRequest, provider: str) -> HttpResponse:
    spec = _spec_or_404(provider)
    instance = ProviderCredential.objects.filter(provider=provider).first()

    if request.method == "POST":
        form = ProviderCredentialForm(request.POST, instance=instance, spec=spec)
        if form.is_valid():
            credential = form.save(commit=False)
            credential.provider = provider
            credential.save()
            messages.success(request, f"Configuration de {spec.name} enregistrée.")
            return redirect("aiproviders:list")
    else:
        form = ProviderCredentialForm(instance=instance, spec=spec)

    return render(
        request,
        "aiproviders/credential_form.html",
        {
            "form": form,
            "spec": spec,
            "credential": instance,
            # Le menu déroulant des modèles suppose des credentials utilisables :
            # sans clé enregistrée, le catalogue est hors de portée et le champ
            # reste une saisie libre.
            "offers_model_picker": spec.supports_model_listing
            and instance is not None
            and instance.is_configured,
        },
    )


@login_required
@staff_required
@require_POST
def credential_test(request: HttpRequest, provider: str) -> HttpResponse:
    """Test de connexion déclenché en HTMX depuis la liste des fournisseurs."""
    spec = _spec_or_404(provider)
    credential = ProviderCredential.objects.filter(provider=provider).first()

    if credential is None or not credential.is_configured:
        result = {"ok": False, "message": f"{spec.name} n'est pas encore configuré."}
    else:
        try:
            ping = get_client(credential).ping()
            result = {"ok": ping.ok, "message": ping.message}
        except ProviderError as exc:
            result = {"ok": False, "message": str(exc)}

    return render(request, "aiproviders/partials/test_result.html", {"result": result})


@login_required
@staff_required
def credential_models(request: HttpRequest, provider: str) -> HttpResponse:
    """Menu déroulant des modèles du fournisseur, chargé en HTMX.

    Le catalogue vit chez le fournisseur : le charger à l'affichage du
    formulaire rendrait l'écran tributaire d'un appel réseau. Il arrive donc
    après coup, et son échec laisse le champ saisissable à la main.
    """
    spec = _spec_or_404(provider)
    if not spec.supports_model_listing:
        raise Http404(f"{spec.name} ne publie pas la liste de ses modèles.")

    credential = ProviderCredential.objects.filter(provider=provider).first()
    models: list = []
    error = None

    if credential is None or not credential.is_configured:
        error = f"Enregistre d'abord une clé pour consulter les modèles de {spec.name}."
    else:
        try:
            models = get_client(credential).list_models()
        except ProviderError as exc:
            error = str(exc)

    return render(
        request,
        "aiproviders/partials/model_choices.html",
        {
            "spec": spec,
            "models": models,
            "error": error,
            "selected": credential.default_model if credential else "",
        },
    )
