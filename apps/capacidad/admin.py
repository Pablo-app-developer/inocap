from django.contrib import admin

from .models import (
    CapacidadSala,
    Novedad,
    ParametroMensual,
    ResumenMensual,
    TerminoAdicional,
)
from .services import orm


class NovedadInline(admin.TabularInline):
    model = Novedad
    extra = 0


class TerminoAdicionalInline(admin.TabularInline):
    model = TerminoAdicional
    extra = 0


@admin.register(ParametroMensual)
class ParametroMensualAdmin(admin.ModelAdmin):
    list_display = ("unidad_negocio", "anio", "mes", "modo", "dias_lav", "sabados_semana", "semanas_mes")
    list_filter = ("unidad_negocio", "anio", "modo")


@admin.register(CapacidadSala)
class CapacidadSalaAdmin(admin.ModelAdmin):
    list_display = (
        "sala", "parametro", "citas_dia_lav", "citas_mes",
        "citas_mes_total", "neto_capacidad_ajustada",
    )
    list_filter = ("parametro__unidad_negocio", "parametro__anio", "parametro__mes", "sala__sede")
    search_fields = ("sala__nombre",)
    readonly_fields = (
        "citas_dia_lav", "citas_dia_sabado", "citas_mes",
        "citas_mes_total", "neto_capacidad_ajustada",
    )
    inlines = [NovedadInline, TerminoAdicionalInline]
    actions = ["recalcular_seleccionadas"]

    @admin.action(description="Recalcular capacidad (snapshot)")
    def recalcular_seleccionadas(self, request, queryset):
        for cap in queryset:
            orm.recalcular(cap)
        self.message_user(request, f"{queryset.count()} capacidad(es) recalculada(s).")

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        # Recalcular tras guardar inlines (novedades/términos/patrones).
        orm.recalcular(form.instance)


@admin.register(ResumenMensual)
class ResumenMensualAdmin(admin.ModelAdmin):
    list_display = ("unidad_negocio", "anio", "mes", "meta_atenciones", "atenciones_realizadas")
    list_filter = ("unidad_negocio", "anio")
