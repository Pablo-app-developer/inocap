"""
Selectors: consultas de lectura para las vistas (sin lógica de escritura).

`vista_mensual` arma la estructura de la "hoja de mes": salas agrupadas por sede,
con subtotales por sede y total general, más el indicador de cumplimiento.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from apps.calendario.services import conteo_mes, festivos_del_mes
from apps.core.models import UnidadNegocio

from .models import CapacidadSala, ParametroMensual, ResumenMensual


@dataclass
class GrupoSede:
    sede: object
    filas: list = field(default_factory=list)
    subtotal_citas_mes: int = 0
    subtotal_neto: int = 0


@dataclass
class VistaMensual:
    unidad: UnidadNegocio
    anio: int
    mes: int
    parametro: ParametroMensual | None
    grupos: list = field(default_factory=list)
    total_citas_mes: int = 0
    total_neto: int = 0
    resumen: ResumenMensual | None = None
    meta_atenciones: int = 0
    cumplimiento_pct: Decimal | None = None
    cumplimiento_estado: str = ""  # "ok" | "warn" | "bad"
    # Conteo real del calendario del mes (transparencia del cálculo)
    dias_lav_reales: int = 0
    sabados_reales: int = 0
    festivos_count: int = 0


def vista_mensual(unidad: UnidadNegocio, anio: int, mes: int) -> VistaMensual:
    parametro = ParametroMensual.objects.filter(
        unidad_negocio=unidad, anio=anio, mes=mes
    ).first()

    capacidades = (
        CapacidadSala.objects.filter(
            sala__unidad_negocio=unidad, parametro__anio=anio, parametro__mes=mes
        )
        .select_related("sala", "sala__sede")
        .prefetch_related("novedades")
        .order_by("sala__sede__nombre", "sala__orden", "sala__nombre")
    )

    grupos: dict[int, GrupoSede] = {}
    total_citas_mes = 0
    total_neto = 0
    for cap in capacidades:
        sede = cap.sala.sede
        g = grupos.get(sede.id)
        if g is None:
            g = grupos[sede.id] = GrupoSede(sede=sede)
        g.filas.append(cap)
        g.subtotal_citas_mes += cap.citas_mes
        g.subtotal_neto += cap.neto_capacidad_ajustada
        total_citas_mes += cap.citas_mes
        total_neto += cap.neto_capacidad_ajustada

    resumen = ResumenMensual.objects.filter(
        unidad_negocio=unidad, anio=anio, mes=mes
    ).first()

    # Meta = override manual del resumen o, si no, el neto total calculado.
    meta = None
    if resumen and resumen.meta_atenciones is not None:
        meta = resumen.meta_atenciones
    else:
        meta = total_neto

    cumplimiento = None
    estado = ""
    if resumen and meta:
        cumplimiento = (Decimal(resumen.atenciones_realizadas) / Decimal(meta)) if meta else None
        if cumplimiento is not None:
            pct = cumplimiento * 100
            estado = "ok" if pct >= 95 else "warn" if pct >= 80 else "bad"

    conteo = conteo_mes(anio, mes)
    festivos_count = len(festivos_del_mes(anio, mes))

    return VistaMensual(
        unidad=unidad,
        anio=anio,
        mes=mes,
        parametro=parametro,
        grupos=sorted(grupos.values(), key=lambda g: g.sede.nombre),
        total_citas_mes=total_citas_mes,
        total_neto=total_neto,
        resumen=resumen,
        meta_atenciones=meta,
        cumplimiento_pct=cumplimiento,
        cumplimiento_estado=estado,
        dias_lav_reales=conteo.dias_lav,
        sabados_reales=conteo.sabados,
        festivos_count=festivos_count,
    )


def periodos_disponibles(unidad: UnidadNegocio) -> list[tuple[int, int]]:
    """(anio, mes) con parámetros cargados para una unidad, desc."""
    return list(
        ParametroMensual.objects.filter(unidad_negocio=unidad)
        .order_by("-anio", "-mes")
        .values_list("anio", "mes")
    )
