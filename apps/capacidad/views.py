"""
Vistas de capacidad instalada (server-rendered + HTMX).

- dashboard: KPIs por unidad de negocio.
- mensual:   "hoja de mes" con salas agrupadas por sede, subtotales y total general.
- editar_capacidad: edición inline HTMX de una fila con recálculo del snapshot.
- fila_capacidad:   devuelve una fila en modo lectura (para cancelar la edición).
"""

from __future__ import annotations

import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.core.models import MetodoCalculo, UnidadNegocio

from . import selectors
from .forms import CapacidadSalaForm, CapacidadSemanalForm, NovedadForm
from .models import MESES, CapacidadSala, Novedad, ParametroMensual, Signo, TipoNovedad
from .services import meses, orm


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


def _seleccion_periodo(request):
    """Resuelve (unidades, unidad, periodos, anio, mes) desde los filtros GET.

    Devuelve None si no hay unidades de negocio activas.
    """
    unidades = list(UnidadNegocio.objects.filter(activo=True))
    if not unidades:
        return None
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
    return unidades, unidad, periodos, anio, mes


@login_required
def mensual(request):
    sel = _seleccion_periodo(request)
    if sel is None:
        return render(request, "capacidad/mensual.html", {"sin_datos": True, "seccion": "mensual"})
    unidades, unidad, periodos, anio, mes = sel

    sig_anio, sig_mes = meses.siguiente_periodo(unidad)
    origen = meses.ultimo_parametro(unidad)

    ctx = _tabla_context(unidad, anio, mes)
    ctx.update(
        {
            "unidades": unidades,
            "unidad_sel": unidad,
            "periodos": periodos,
            "anio_sel": anio,
            "mes_sel": mes,
            "seccion": "mensual",
            "sig_anio": sig_anio,
            "sig_mes": sig_mes,
            "origen_mes": origen,
        }
    )
    return render(request, "capacidad/mensual.html", ctx)


@login_required
@require_POST
def crear_mes(request):
    """Crea un mes nuevo clonando la parametrización del último mes cargado."""
    unidad = get_object_or_404(UnidadNegocio, pk=request.POST.get("unidad"))
    try:
        anio = int(request.POST.get("anio", ""))
        mes = int(request.POST.get("mes", ""))
        if not (1 <= mes <= 12 and 2000 <= anio <= 2100):
            raise ValueError("Periodo fuera de rango.")
        nuevo = meses.crear_mes(unidad, anio, mes)
    except ValueError as e:
        messages.error(request, str(e) or "Periodo inválido.")
        return redirect(f"{reverse('capacidad:mensual')}?unidad={unidad.id}")

    messages.success(
        request,
        f"{nuevo.get_mes_display()} {nuevo.anio} creado copiando la parametrización "
        f"del último mes. Registra sus novedades cuando ocurran.",
    )
    return redirect(
        f"{reverse('capacidad:mensual')}?unidad={unidad.id}&anio={anio}&mes={mes}"
    )


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
@require_POST
def cambiar_metodo(request, pk):
    """Cambia el método de cálculo de la sala (afecta todos sus meses) y recalcula."""
    cap = get_object_or_404(
        CapacidadSala.objects.select_related("sala", "parametro"), pk=pk
    )
    metodo = request.POST.get("metodo")
    if metodo in MetodoCalculo.values:
        cap.sala.metodo_calculo = metodo
        cap.sala.save(update_fields=["metodo_calculo"])
    return _tabla_actualizada(request, cap)


@login_required
def fila_capacidad(request, pk):
    cap = get_object_or_404(
        CapacidadSala.objects.select_related("sala", "parametro"), pk=pk
    )
    return render(request, "capacidad/partials/_fila.html", {"cap": cap})


# --------------------------------------------------------------------------- #
# Módulo de novedades
# --------------------------------------------------------------------------- #
def _ctx_novedades(unidad, anio, mes, error=None):
    vm = selectors.vista_mensual(unidad, anio, mes)
    abierto = bool(vm.parametro and vm.parametro.novedades_abiertas)
    return {
        "vm": vm,
        "abierto": abierto,
        "error": error,
        "tipos": TipoNovedad.choices,
        "signos": Signo.choices,
    }


@login_required
def novedades(request):
    """Módulo de ingreso de novedades del mes (por sala)."""
    sel = _seleccion_periodo(request)
    if sel is None:
        return render(request, "capacidad/novedades.html", {"sin_datos": True, "seccion": "novedades"})
    unidades, unidad, periodos, anio, mes = sel

    ctx = _ctx_novedades(unidad, anio, mes)
    ctx.update(
        {
            "unidades": unidades,
            "unidad_sel": unidad,
            "periodos": periodos,
            "anio_sel": anio,
            "mes_sel": mes,
            "meses": MESES,
            "seccion": "novedades",
        }
    )
    return render(request, "capacidad/novedades.html", ctx)


def _modulo_novedades_actualizado(request, parametro, error=None):
    ctx = _ctx_novedades(parametro.unidad_negocio, parametro.anio, parametro.mes, error=error)
    return render(request, "capacidad/partials/_novedades_modulo.html", ctx)


@login_required
@require_POST
def agregar_novedad(request, cap_id):
    cap = get_object_or_404(
        CapacidadSala.objects.select_related("sala", "parametro__unidad_negocio"),
        pk=cap_id,
    )
    if not cap.parametro.novedades_abiertas:
        return _modulo_novedades_actualizado(
            request, cap.parametro,
            error="El ingreso de novedades de este mes no está habilitado.",
        )

    form = NovedadForm(request.POST)
    if form.is_valid():
        novedad = form.save(commit=False)
        novedad.capacidad_sala = cap
        novedad.save()
        orm.recalcular(cap)
        error = None
    else:
        detalles = "; ".join(
            f"{campo}: {', '.join(errs)}" for campo, errs in form.errors.items()
        )
        error = f"No se pudo registrar la novedad de {cap.sala.nombre}. {detalles}"
    return _modulo_novedades_actualizado(request, cap.parametro, error=error)


@login_required
@require_POST
def eliminar_novedad(request, pk):
    novedad = get_object_or_404(
        Novedad.objects.select_related(
            "capacidad_sala__sala", "capacidad_sala__parametro__unidad_negocio"
        ),
        pk=pk,
    )
    cap = novedad.capacidad_sala
    if not cap.parametro.novedades_abiertas:
        return _modulo_novedades_actualizado(
            request, cap.parametro,
            error="El ingreso de novedades de este mes no está habilitado.",
        )
    novedad.delete()
    orm.recalcular(cap)
    return _modulo_novedades_actualizado(request, cap.parametro)


@login_required
def editar_novedad(request, pk):
    """Edición inline de una novedad ya registrada (solo si el mes está habilitado)."""
    novedad = get_object_or_404(
        Novedad.objects.select_related(
            "capacidad_sala__sala", "capacidad_sala__parametro__unidad_negocio"
        ),
        pk=pk,
    )
    cap = novedad.capacidad_sala
    abierto = cap.parametro.novedades_abiertas

    if request.method == "POST":
        if not abierto:
            return _modulo_novedades_actualizado(
                request, cap.parametro,
                error="El ingreso de novedades de este mes no está habilitado.",
            )
        form = NovedadForm(request.POST, instance=novedad)
        if form.is_valid():
            form.save()
            orm.recalcular(cap)
            return _modulo_novedades_actualizado(request, cap.parametro)
        return render(
            request, "capacidad/partials/_novedad_form.html",
            {"form": form, "n": novedad, "abierto": abierto},
        )

    if not abierto:
        return render(
            request, "capacidad/partials/_novedad_fila.html",
            {"n": novedad, "abierto": abierto},
        )
    form = NovedadForm(instance=novedad)
    return render(
        request, "capacidad/partials/_novedad_form.html",
        {"form": form, "n": novedad, "abierto": abierto},
    )


@login_required
def fila_novedad(request, pk):
    """Devuelve la fila de una novedad en modo lectura (botón Cancelar)."""
    novedad = get_object_or_404(
        Novedad.objects.select_related("capacidad_sala__parametro"), pk=pk
    )
    abierto = novedad.capacidad_sala.parametro.novedades_abiertas
    return render(
        request, "capacidad/partials/_novedad_fila.html",
        {"n": novedad, "abierto": abierto},
    )


@login_required
@require_POST
def toggle_novedades(request):
    """Habilita/deshabilita el ingreso de novedades de un mes (solo admin)."""
    if not request.user.is_staff:
        messages.error(request, "Solo un administrador puede habilitar o cerrar el mes.")
        return redirect(reverse("capacidad:novedades"))

    parametro = get_object_or_404(ParametroMensual, pk=request.POST.get("parametro"))
    parametro.novedades_abiertas = not parametro.novedades_abiertas
    parametro.save(update_fields=["novedades_abiertas"])
    estado = "habilitado" if parametro.novedades_abiertas else "cerrado"
    messages.success(
        request,
        f"Ingreso de novedades de {parametro.get_mes_display()} {parametro.anio} {estado}.",
    )
    return redirect(
        f"{reverse('capacidad:novedades')}?unidad={parametro.unidad_negocio_id}"
        f"&anio={parametro.anio}&mes={parametro.mes}"
    )
