"""
Vistas de proyección monetaria: "Capacidad en $" (por mes) y "Resumen anual"
(indicador de cumplimiento del año completo, hoja RESUMEN del Excel).
"""

import datetime
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.capacidad import selectors as capacidad_selectors
from apps.capacidad.models import MESES
from apps.capacidad.views import _entero, _seleccion_periodo
from apps.core import accesos

from .services.dinero import proyeccion_dinero


@login_required
def dinero(request):
    sel = _seleccion_periodo(request)
    if sel is None:
        return render(request, "atenciones/dinero.html", {"sin_datos": True, "seccion": "dinero"})
    unidades, unidad, periodos, anio, mes = sel

    proyeccion = proyeccion_dinero(unidad, anio, mes)
    return render(request, "atenciones/dinero.html", {
        "unidades": unidades,
        "unidad_sel": unidad,
        "periodos": periodos,
        "anio_sel": anio,
        "mes_sel": mes,
        "meses": MESES,
        "seccion": "dinero",
        "p": proyeccion,
    })


def _fila_resumen_anual(unidad, anio: int, mes: int, nombre_mes: str) -> dict:
    """Una fila de la tabla anual: capacidad/atenciones (app capacidad) +
    proyección monetaria (app atenciones) + presupuesto (ResumenMensual)."""
    vm = capacidad_selectors.vista_mensual(unidad, anio, mes)
    proy = proyeccion_dinero(unidad, anio, mes)
    resumen = vm.resumen

    meta = vm.meta_atenciones or 0
    realizadas = resumen.atenciones_realizadas if resumen else 0
    cumpl_atenciones = (Decimal(realizadas) / meta * 100) if meta else None

    estandar = proy.valor_total
    facturado = resumen.valor_facturado if resumen else Decimal("0")
    cumpl_dinero = (facturado / estandar * 100) if estandar else None

    presupuesto = resumen.presupuesto if resumen else Decimal("0")
    meta_pct = resumen.meta_pct if resumen else Decimal("0.10")
    meta_10 = presupuesto * meta_pct

    return {
        "mes": nombre_mes,
        "meta_atenciones": meta,
        "atenciones_realizadas": realizadas,
        "cumpl_atenciones": cumpl_atenciones,
        "estandar_capacidad": estandar,
        "facturado_contab": facturado,
        "cumpl_dinero": cumpl_dinero,
        "presupuesto": presupuesto,
        "meta_10": meta_10,
        "presupuesto_mas_meta": presupuesto + meta_10,
    }


@login_required
def resumen_anual(request):
    """Indicador anual por unidad de negocio: tabla + gráficas mensuales
    (atenciones vs meta, facturado vs estándar de capacidad en $), ambas con
    una línea de referencia al 90 %."""
    unidades = list(accesos.unidades_accesibles(request.user))
    if not unidades:
        return render(
            request, "atenciones/resumen_anual.html",
            {"sin_datos": True, "seccion": "resumen_anual"},
        )

    unidad_id = request.GET.get("unidad")
    unidad = next((u for u in unidades if str(u.id) == unidad_id), unidades[0])

    periodos = capacidad_selectors.periodos_disponibles(unidad)
    anio_defecto = periodos[0][0] if periodos else datetime.date.today().year
    anio = _entero(request.GET.get("anio"), anio_defecto)

    filas = [_fila_resumen_anual(unidad, anio, mes, nombre) for mes, nombre in MESES]

    total = {
        "meta_atenciones": sum(f["meta_atenciones"] for f in filas),
        "atenciones_realizadas": sum(f["atenciones_realizadas"] for f in filas),
        "estandar_capacidad": sum((f["estandar_capacidad"] for f in filas), Decimal("0")),
        "facturado_contab": sum((f["facturado_contab"] for f in filas), Decimal("0")),
        "presupuesto": sum((f["presupuesto"] for f in filas), Decimal("0")),
        "meta_10": sum((f["meta_10"] for f in filas), Decimal("0")),
        "presupuesto_mas_meta": sum((f["presupuesto_mas_meta"] for f in filas), Decimal("0")),
    }
    total["cumpl_atenciones"] = (
        Decimal(total["atenciones_realizadas"]) / total["meta_atenciones"] * 100
        if total["meta_atenciones"] else None
    )
    total["cumpl_dinero"] = (
        total["facturado_contab"] / total["estandar_capacidad"] * 100
        if total["estandar_capacidad"] else None
    )

    grafica_atenciones = {
        "labels": [f["mes"] for f in filas],
        "realizadas": [f["atenciones_realizadas"] for f in filas],
        "meta": [f["meta_atenciones"] for f in filas],
        "meta_90": [round(f["meta_atenciones"] * 0.9) for f in filas],
    }
    grafica_dinero = {
        "labels": [f["mes"] for f in filas],
        "facturado": [float(f["facturado_contab"]) for f in filas],
        "estandar": [float(f["estandar_capacidad"]) for f in filas],
        "meta_90": [float(f["estandar_capacidad"] * Decimal("0.9")) for f in filas],
    }

    return render(request, "atenciones/resumen_anual.html", {
        "unidades": unidades,
        "unidad_sel": unidad,
        "periodos": periodos,
        "anio_sel": anio,
        "filas": filas,
        "total": total,
        "grafica_atenciones": grafica_atenciones,
        "grafica_dinero": grafica_dinero,
        "seccion": "resumen_anual",
    })
