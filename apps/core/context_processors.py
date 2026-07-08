from .accesos import unidades_accesibles


def unidades_sidebar(request):
    """Unidades de negocio del menú lateral (solo usuarios autenticados)."""
    if not request.user.is_authenticated:
        return {}
    return {
        "unidades_sidebar": unidades_accesibles(request.user).order_by("orden", "nombre")
    }
