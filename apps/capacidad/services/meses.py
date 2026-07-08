"""
Creación de un mes nuevo clonando la parametrización del último mes existente.

Copia lo estructural (parámetros de la unidad y ENTRADAS de cada sala: horas,
tiempo estándar, citas por día de la semana, overrides, términos y horario).
NO copia lo específico de cada mes: novedades, ajuste por sobreatención ni
observaciones. Las salas se toman de las ACTIVAS actuales: una sala nueva entra
con valores en cero y una desactivada ya no aparece.
"""

from __future__ import annotations

from django.db import transaction

from apps.core.models import UnidadNegocio

from ..models import CapacidadSala, ParametroMensual, TerminoAdicional
from . import orm

# Entradas de CapacidadSala que se conservan de un mes a otro.
CAMPOS_ENTRADA = [
    "horas_dia_lav",
    "horas_dia_sabado",
    "tiempo_estandar_horas",
    "override_dias_lav",
    "override_sabados",
    "citas_lun", "citas_mar", "citas_mie", "citas_jue",
    "citas_vie", "citas_sab", "citas_dom",
    "sabados_alternos",
    "horario_laboral",
]

CAMPOS_PARAMETRO = [
    "modo", "dias_lav", "sabados_semana", "semanas_mes",
    "minutos_hora", "tiempo_por_cita_min",
]


def ultimo_parametro(unidad: UnidadNegocio) -> ParametroMensual | None:
    return (
        ParametroMensual.objects.filter(unidad_negocio=unidad)
        .order_by("-anio", "-mes")
        .first()
    )


def siguiente_periodo(unidad: UnidadNegocio) -> tuple[int, int]:
    """(anio, mes) siguiente al último mes cargado (o el actual si no hay ninguno)."""
    origen = ultimo_parametro(unidad)
    if origen is None:
        import datetime

        hoy = datetime.date.today()
        return hoy.year, hoy.month
    if origen.mes == 12:
        return origen.anio + 1, 1
    return origen.anio, origen.mes + 1


@transaction.atomic
def crear_mes(unidad: UnidadNegocio, anio: int, mes: int) -> ParametroMensual:
    """Crea el mes (anio, mes) para la unidad clonando el último mes existente.

    Lanza ValueError si el mes ya existe.
    """
    if ParametroMensual.objects.filter(unidad_negocio=unidad, anio=anio, mes=mes).exists():
        raise ValueError(f"{unidad} ya tiene cargado {mes}/{anio}.")

    origen = ultimo_parametro(unidad)

    datos_param = (
        {campo: getattr(origen, campo) for campo in CAMPOS_PARAMETRO} if origen else {}
    )
    nuevo = ParametroMensual.objects.create(
        unidad_negocio=unidad, anio=anio, mes=mes, **datos_param
    )

    previas = {}
    if origen:
        previas = {
            c.sala_id: c
            for c in CapacidadSala.objects.filter(parametro=origen).prefetch_related("terminos")
        }

    for sala in unidad.salas.filter(activo=True):
        base = previas.get(sala.id)
        cap = CapacidadSala(sala=sala, parametro=nuevo)
        if base is not None:
            for campo in CAMPOS_ENTRADA:
                setattr(cap, campo, getattr(base, campo))
        cap.save()
        if base is not None:
            TerminoAdicional.objects.bulk_create(
                TerminoAdicional(
                    capacidad_sala=cap,
                    descripcion=t.descripcion,
                    citas=t.citas,
                    periodicidad=t.periodicidad,
                )
                for t in base.terminos.all()
            )
        orm.recalcular(cap)

    return nuevo
