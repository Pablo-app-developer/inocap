"""
Adaptadores ORM del motor de cálculo.

Traducen los modelos Django a las dataclasses puras de `calculo`, ejecutan el
cálculo y persisten el snapshot (citas_dia, citas_mes, neto...) en CapacidadSala.
"""

from __future__ import annotations

from decimal import Decimal

from apps.calendario.services import (
    conteo_mes,
    festivos_del_mes,
    ocurrencias_por_dia,
)
from apps.core.models import MetodoCalculo

from . import calculo
from .calculo import (
    DiasMes,
    EntradaCapacidad,
    Novedad,
    ResultadoCapacidad,
    Termino,
)


def _dias_mes(capacidad) -> DiasMes:
    """Construye DiasMes según el modo del parámetro y overrides de la sala."""
    p = capacidad.parametro
    # Solo POR_HORAS cuenta días reales del calendario. PERSONALIZADO es una
    # "receta semanal" (× semanas): usa siempre los parámetros fijos + overrides.
    usar_calendario = (
        p.modo == calculo.MODO_CALENDARIO
        and capacidad.sala.metodo_calculo == MetodoCalculo.POR_HORAS
    )
    if usar_calendario:
        conteo = conteo_mes(p.anio, p.mes)
        dias_lav, sabados = conteo.dias_lav, conteo.sabados
    else:
        dias_lav, sabados = p.dias_lav, p.sabados_semana

    # Overrides estructurados (método PERSONALIZADO) reemplazan el conteo.
    if capacidad.override_dias_lav is not None:
        dias_lav = capacidad.override_dias_lav
    if capacidad.override_sabados is not None:
        sabados = capacidad.override_sabados

    if not capacidad.sala.atiende_sabados:
        sabados = 0

    return DiasMes(dias_lav=dias_lav, sabados=sabados, semanas=p.semanas_mes)


def _ocurrencias_dias(capacidad) -> tuple:
    """Veces que ocurre cada día (0=lun … 6=dom) en el mes, según el modo.

    CALENDARIO: ocurrencias reales del calendario descontando festivos.
    EXCEL_LEGACY: cada día L–V y sábado ocurre `semanas_mes` veces (fijo).
    Si la sala no atiende sábados, el sábado se pone en 0; si atiende un
    sábado de por medio (`sabados_alternos`), cuenta la mitad (piso).
    """
    p = capacidad.parametro
    if p.modo == calculo.MODO_CALENDARIO:
        occ = list(ocurrencias_por_dia(p.anio, p.mes, festivos_del_mes(p.anio, p.mes)))
    else:
        # Lun–Sáb ocurren `semanas_mes` veces; domingo 0.
        occ = [p.semanas_mes] * 6 + [0]

    if not capacidad.sala.atiende_sabados:
        occ[5] = 0  # sábado
    elif capacidad.sabados_alternos:
        occ[5] //= 2  # un sábado de por medio (quincenal)
    return tuple(occ)


def construir_entrada(capacidad) -> EntradaCapacidad:
    """Arma la EntradaCapacidad pura a partir de una CapacidadSala (con relaciones)."""
    terminos = [
        Termino(citas=t.citas, periodicidad=t.periodicidad)
        for t in capacidad.terminos.all()
    ]
    novedades = [
        Novedad(citas=n.citas_afectadas, signo=n.signo)
        for n in capacidad.novedades.all()
    ]
    metodo = capacidad.sala.metodo_calculo
    # PERSONALIZADO se calcula siempre como receta semanal (× semanas), incluso si
    # la unidad está en modo CALENDARIO. El resto respeta el modo del parámetro.
    modo_efectivo = (
        calculo.MODO_EXCEL_LEGACY
        if metodo == MetodoCalculo.PERSONALIZADO
        else capacidad.parametro.modo
    )
    return EntradaCapacidad(
        metodo=metodo,
        modo=modo_efectivo,
        dias=_dias_mes(capacidad),
        horas_dia_lav=Decimal(capacidad.horas_dia_lav),
        horas_dia_sabado=Decimal(capacidad.horas_dia_sabado),
        tiempo_estandar_horas=Decimal(capacidad.tiempo_estandar_horas),
        ajuste_sobreatencion=capacidad.ajuste_sobreatencion,
        terminos=terminos,
        citas_dias=capacidad.citas_por_dia_semana,
        ocurrencias_dias=_ocurrencias_dias(capacidad),
        novedades=novedades,
    )


def calcular(capacidad) -> ResultadoCapacidad:
    """Calcula sin persistir."""
    return calculo.calcular_capacidad(construir_entrada(capacidad))


def recalcular(capacidad, guardar: bool = True) -> ResultadoCapacidad:
    """Calcula y escribe el snapshot en la CapacidadSala."""
    r = calcular(capacidad)
    capacidad.citas_dia_lav = r.citas_dia_lav
    capacidad.citas_dia_sabado = r.citas_dia_sabado
    capacidad.citas_mes = r.citas_mes
    capacidad.citas_mes_total = r.citas_mes_total
    capacidad.neto_capacidad_ajustada = r.neto
    if guardar:
        capacidad.save(
            update_fields=[
                "citas_dia_lav",
                "citas_dia_sabado",
                "citas_mes",
                "citas_mes_total",
                "neto_capacidad_ajustada",
            ]
        )
    return r


def total_neto_unidad(unidad_negocio, anio: int, mes: int) -> int:
    """Suma de netos de todas las salas de una unidad en un mes (meta de atenciones)."""
    from apps.capacidad.models import CapacidadSala

    valores = CapacidadSala.objects.filter(
        sala__unidad_negocio=unidad_negocio,
        parametro__anio=anio,
        parametro__mes=mes,
    ).values_list("neto_capacidad_ajustada", flat=True)
    return sum(valores)
