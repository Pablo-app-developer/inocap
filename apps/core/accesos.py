"""
Qué unidades de negocio puede ver/operar un usuario (sidebar + control de acceso).

Regla: los superusuarios ven todas las unidades activas. El resto de usuarios
solo ven las unidades asignadas en su `PerfilUsuario` (Django admin > Usuarios).
Un usuario sin perfil o con el M2M vacío no ve ninguna.
"""

from __future__ import annotations

from django.core.exceptions import PermissionDenied

from .models import UnidadNegocio


def unidades_accesibles(user):
    """Unidades de negocio activas visibles para este usuario."""
    qs = UnidadNegocio.objects.filter(activo=True)
    if not user.is_authenticated:
        return qs.none()
    if user.is_superuser:
        return qs
    return qs.filter(perfiles_acceso__usuario=user).distinct()


def tiene_acceso(user, unidad_negocio) -> bool:
    """True si el usuario puede ver/operar la unidad de negocio dada."""
    if user.is_superuser:
        return True
    unidad_id = getattr(unidad_negocio, "pk", unidad_negocio)
    return unidades_accesibles(user).filter(pk=unidad_id).exists()


def verificar_acceso(user, unidad_negocio) -> None:
    """Lanza PermissionDenied (403) si el usuario no tiene acceso a la unidad."""
    if not tiene_acceso(user, unidad_negocio):
        raise PermissionDenied("No tienes acceso a esta unidad de negocio.")
