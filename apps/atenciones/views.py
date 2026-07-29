"""
Vistas de proyección monetaria: "Capacidad en $" (por mes) y "Resumen anual"
(indicador de cumplimiento del año completo, hoja RESUMEN del Excel).
"""

import datetime
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.urls import reverse

from apps.capacidad import selectors as capacidad_selectors
from apps.capacidad.models import MESES, ResumenMensual
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

    capacidad_instalada = vm.total_citas_mes  # bruta, antes de novedades
    meta = vm.meta_atenciones or 0  # ajustada (neta), después de novedades
    realizadas = resumen.atenciones_realizadas if resumen else 0
    cumpl_atenciones = (Decimal(realizadas) / meta * 100) if meta else None

    estandar = proy.valor_total
    facturado = resumen.valor_facturado if resumen else Decimal("0")
    cumpl_dinero = (facturado / estandar * 100) if estandar else None

    presupuesto = resumen.presupuesto if resumen else Decimal("0")
    meta_pct = resumen.meta_pct if resumen else Decimal("0.10")
    meta_10 = presupuesto * meta_pct
    meta_cumplimiento_pct = resumen.meta_cumplimiento_pct if resumen else Decimal("0.90")

    return {
        "mes": nombre_mes,
        "capacidad_instalada": capacidad_instalada,
        "meta_atenciones": meta,
        "atenciones_realizadas": realizadas,
        "cumpl_atenciones": cumpl_atenciones,
        "estandar_capacidad": estandar,
        "facturado_contab": facturado,
        "cumpl_dinero": cumpl_dinero,
        "presupuesto": presupuesto,
        "meta_10": meta_10,
        "presupuesto_mas_meta": presupuesto + meta_10,
        "meta_cumplimiento_pct": meta_cumplimiento_pct,
    }


@login_required
def resumen_anual(request):
    """Indicador anual por unidad de negocio: tabla + gráficas mensuales
    (atenciones vs meta, facturado vs estándar de capacidad en $), ambas con
    una línea de referencia a la meta de cumplimiento (`meta_cumplimiento_pct`
    de ResumenMensual, editable en /facturacion-presupuesto/, 90 % por defecto)."""
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
        "capacidad_instalada": sum(f["capacidad_instalada"] for f in filas),
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
        "meta_cumplimiento": [
            round(f["meta_atenciones"] * f["meta_cumplimiento_pct"]) for f in filas
        ],
    }
    grafica_dinero = {
        "labels": [f["mes"] for f in filas],
        "facturado": [float(f["facturado_contab"]) for f in filas],
        "estandar": [float(f["estandar_capacidad"]) for f in filas],
        "meta_cumplimiento": [
            float(f["estandar_capacidad"] * f["meta_cumplimiento_pct"]) for f in filas
        ],
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


def _decimal(valor, defecto: Decimal) -> Decimal:
    """Decimal tolerante: '' o inválido -> defecto. Acepta coma decimal."""
    if valor is None or str(valor).strip() == "":
        return defecto
    try:
        return Decimal(str(valor).strip().replace(",", "."))
    except InvalidOperation:
        return defecto


@login_required
def facturacion_presupuesto(request):
    """Carga manual de Valor Siesa (facturado), presupuestado y meta de
    cumplimiento, por unidad de negocio y mes — alimenta el Resumen anual."""
    if not request.user.is_staff:
        raise PermissionDenied("Solo un administrador puede cargar facturación y presupuesto.")

    unidades = list(accesos.unidades_accesibles(request.user))
    if not unidades:
        return render(
            request, "atenciones/facturacion_presupuesto.html",
            {"sin_datos": True, "seccion": "facturacion_presupuesto"},
        )

    anio_defecto = datetime.date.today().year
    anio = _entero(request.GET.get("anio") or request.POST.get("anio"), anio_defecto)

    if request.method == "POST":
        for unidad in unidades:
            for mes, _nombre in MESES:
                prefijo = f"{unidad.id}_{mes}"
                ResumenMensual.objects.update_or_create(
                    unidad_negocio=unidad, anio=anio, mes=mes,
                    defaults={
                        "valor_facturado": _decimal(request.POST.get(f"facturado_{prefijo}"), Decimal("0")),
                        "presupuesto": _decimal(request.POST.get(f"presupuesto_{prefijo}"), Decimal("0")),
                        "meta_cumplimiento_pct": _decimal(
                            request.POST.get(f"meta_{prefijo}"), Decimal("90")
                        ) / Decimal("100"),
                    },
                )
        messages.success(request, f"Facturación y presupuesto de {anio} guardados.")
        return redirect(f"{reverse('atenciones:facturacion_presupuesto')}?anio={anio}")

    grupos = []
    for unidad in unidades:
        resumenes = {
            r.mes: r for r in ResumenMensual.objects.filter(unidad_negocio=unidad, anio=anio)
        }
        filas = []
        for mes, nombre in MESES:
            r = resumenes.get(mes)
            filas.append({
                "mes": mes,
                "nombre_mes": nombre,
                "facturado": r.valor_facturado if r else Decimal("0"),
                "presupuesto": r.presupuesto if r else Decimal("0"),
                "meta_pct": (r.meta_cumplimiento_pct * 100) if r else Decimal("90"),
            })
        grupos.append({"unidad": unidad, "filas": filas})

    return render(request, "atenciones/facturacion_presupuesto.html", {
        "grupos": grupos,
        "anio_sel": anio,
        "seccion": "facturacion_presupuesto",
    })
