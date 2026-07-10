"""
Vista "Capacidad en $": proyección monetaria de la capacidad ajustada.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.capacidad.models import MESES
from apps.capacidad.views import _seleccion_periodo

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
