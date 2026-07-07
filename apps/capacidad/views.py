"""
Vistas de capacidad instalada (server-rendered + HTMX).

- dashboard: KPIs por unidad de negocio.
- mensual:   "hoja de mes" con salas agrupadas por sede, subtotales y total general.
- editar_capacidad: edición inline HTMX de una fila con recálculo del snapshot.
- fila_capacidad:   devuelve una fila en modo lectura (para cancelar la edición).
"""

from __future__ import annotations

import datetime

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from apps.core.models import UnidadNegocio

from apps.core.models import MetodoCalculo

from . import selectors
from .forms import CapacidadSalaForm, CapacidadSemanalForm
from .models import MESES, CapacidadSala
from .services import orm


def _tabla_context(unidad, anio, mes):
    vm = selectors.vista_mensual(unidad, anio, mes)
    return {"vm": vm, "meses": MESES}


@login_required
def dashboard(request):
    unidades = UnidadNegocio.objects.filter(activo=True)
    tarjetas = []
    for u in unidades:
        periodos = selectors.periodos_disponibles(u)
        if periodos:
            anio, mes = periodos[0]
            vm = selectors.vista_mensual(u, anio, mes)
        else:
            vm = None
        tarjetas.append({"unidad": u, "vm": vm, "num_salas": u.salas.filter(activo=True).count()})
    return render(request, "capacidad/dashboard.html", {"tarjetas": tarjetas, "seccion": "dashboard"})


@login_required
def mensual(request):
    unidades = list(UnidadNegocio.objects.filter(activo=True))
    if not unidades:
        return render(request, "capacidad/mensual.html", {"sin_datos": True, "seccion": "mensual"})

    # Selección de unidad
    unidad_id = request.GET.get("unidad")
    unidad = next((u for u in unidades if str(u.id) == unidad_id), unidades[0])

    periodos = selectors.periodos_disponibles(unidad)
    hoy = datetime.date.today()
    if periodos:
        anio_def, mes_def = periodos[0]
    else:
        anio_def, mes_def = hoy.year, hoy.month
    anio = int(request.GET.get("anio", anio_def))
    mes = int(request.GET.get("mes", mes_def))

    ctx = _tabla_context(unidad, anio, mes)
    ctx.update(
        {
            "unidades": unidades,
            "unidad_sel": unidad,
            "periodos": periodos,
            "anio_sel": anio,
            "mes_sel": mes,
            "seccion": "mensual",
        }
    )
    return render(request, "capacidad/mensual.html", ctx)


def _tabla_actualizada(request, cap):
    """Re-renderiza toda la tabla (subtotales y total) tras recalcular una fila."""
    orm.recalcular(cap)
    ctx = _tabla_context(cap.sala.unidad_negocio, cap.parametro.anio, cap.parametro.mes)
    ctx["fila_actualizada_id"] = cap.id
    return render(request, "capacidad/partials/_tabla.html", ctx)


@login_required
def editar_capacidad(request, pk):
    cap = get_object_or_404(
        CapacidadSala.objects.select_related("sala", "parametro"), pk=pk
    )

    # POR_DIA_SEMANA se edita por "citas por semana"; el resto por horas.
    es_semanal = cap.sala.metodo_calculo == MetodoCalculo.POR_DIA_SEMANA
    FormClass = CapacidadSemanalForm if es_semanal else CapacidadSalaForm
    plantilla = (
        "capacidad/partials/_fila_form_semanal.html"
        if es_semanal
        else "capacidad/partials/_fila_form.html"
    )

    if request.method == "POST":
        form = FormClass(request.POST, instance=cap)
        if form.is_valid():
            form.save()
            return _tabla_actualizada(request, cap)
    else:
        form = FormClass(instance=cap)
    return render(request, plantilla, {"form": form, "cap": cap})


@login_required
def fila_capacidad(request, pk):
    cap = get_object_or_404(
        CapacidadSala.objects.select_related("sala", "parametro"), pk=pk
    )
    return render(request, "capacidad/partials/_fila.html", {"cap": cap})
