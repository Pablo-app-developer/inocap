from django.contrib import admin

from .models import (
    Atencion,
    CodigoServicioGrupo,
    Entidad,
    GrupoServicio,
    MapeoEspecialidad,
    TarifaConvenio,
)


class CodigoServicioGrupoInline(admin.TabularInline):
    model = CodigoServicioGrupo
    extra = 0


@admin.register(GrupoServicio)
class GrupoServicioAdmin(admin.ModelAdmin):
    list_display = ("nombre", "unidad_negocio", "orden", "es_otras")
    list_filter = ("unidad_negocio",)
    list_editable = ("orden",)
    inlines = [CodigoServicioGrupoInline]


@admin.register(Entidad)
class EntidadAdmin(admin.ModelAdmin):
    list_display = ("nombre", "nit", "creada_automaticamente")
    list_filter = ("creada_automaticamente",)
    search_fields = ("nombre", "nit")


@admin.register(TarifaConvenio)
class TarifaConvenioAdmin(admin.ModelAdmin):
    list_display = ("entidad", "codigo_servicio", "nombre_servicio", "valor", "tipo_contratacion")
    list_filter = ("tipo_contratacion",)
    search_fields = ("entidad__nombre", "codigo_servicio", "nombre_servicio")


@admin.register(MapeoEspecialidad)
class MapeoEspecialidadAdmin(admin.ModelAdmin):
    list_display = ("especialidad", "unidad_negocio")
    list_filter = ("unidad_negocio",)


@admin.register(Atencion)
class AtencionAdmin(admin.ModelAdmin):
    list_display = ("fecha", "codigo_servicio", "nombre_servicio", "estado",
                    "entidad", "unidad_negocio", "sede_nombre")
    list_filter = ("estado", "unidad_negocio", "anio", "mes")
    search_fields = ("codigo_servicio", "nombre_servicio", "entidad__nombre")
    date_hierarchy = "fecha"
