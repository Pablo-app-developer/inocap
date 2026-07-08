from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin

from .models import PerfilUsuario, Sala, Sede, UnidadNegocio


@admin.register(UnidadNegocio)
class UnidadNegocioAdmin(admin.ModelAdmin):
    list_display = ("nombre", "codigo", "activo", "orden")
    prepopulated_fields = {"codigo": ("nombre",)}
    list_editable = ("activo", "orden")


@admin.register(Sede)
class SedeAdmin(admin.ModelAdmin):
    list_display = ("nombre", "codigo", "es_municipal", "orden", "activo")
    prepopulated_fields = {"codigo": ("nombre",)}
    list_filter = ("es_municipal", "activo")
    list_editable = ("orden", "activo")


@admin.register(Sala)
class SalaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "unidad_negocio", "sede", "especialidad", "metodo_calculo", "activo")
    list_filter = ("unidad_negocio", "sede", "metodo_calculo", "activo")
    search_fields = ("nombre", "especialidad")


class PerfilUsuarioInline(admin.StackedInline):
    model = PerfilUsuario
    can_delete = False
    verbose_name_plural = "Acceso a unidades de negocio"
    filter_horizontal = ("unidades_negocio",)


class PerfilUserAdmin(UserAdmin):
    """UserAdmin estándar + el inline de unidades de negocio accesibles.

    Los superusuarios ven todas las unidades automáticamente (no necesitan
    perfil); este inline solo importa para usuarios normales.
    """

    inlines = [PerfilUsuarioInline]


User = get_user_model()
admin.site.unregister(User)
admin.site.register(User, PerfilUserAdmin)
