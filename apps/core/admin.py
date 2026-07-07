from django.contrib import admin

from .models import Sala, Sede, UnidadNegocio


@admin.register(UnidadNegocio)
class UnidadNegocioAdmin(admin.ModelAdmin):
    list_display = ("nombre", "codigo", "activo", "orden")
    prepopulated_fields = {"codigo": ("nombre",)}
    list_editable = ("activo", "orden")


@admin.register(Sede)
class SedeAdmin(admin.ModelAdmin):
    list_display = ("nombre", "codigo", "es_municipal", "activo")
    prepopulated_fields = {"codigo": ("nombre",)}
    list_filter = ("es_municipal", "activo")


@admin.register(Sala)
class SalaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "unidad_negocio", "sede", "especialidad", "metodo_calculo", "activo")
    list_filter = ("unidad_negocio", "sede", "metodo_calculo", "activo")
    search_fields = ("nombre", "especialidad")
