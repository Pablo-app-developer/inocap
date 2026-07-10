"""
Mezclas de servicios y entidades a partir de las atenciones reales.

Reglas de negocio (confirmadas con el usuario):
  - Solo cuentan las atenciones con estado 'Salida' (realizadas).
  - La mezcla se calcula sobre el MISMO mes (no acumulado del año).
  - Se usan TODAS las entidades (sin agrupar en "otras").
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Count

from apps.core.models import UnidadNegocio

from .models import ESTADO_REALIZADA, Atencion, GrupoServicio


@dataclass(frozen=True)
class ItemMezcla:
    clave: str          # código de servicio o nombre de entidad
    nombre: str
    conteo: int
    porcentaje: Decimal  # fracción 0..1 (no ×100)


def _con_porcentajes(filas, total) -> list[ItemMezcla]:
    if not total:
        return []
    return [
        ItemMezcla(
            clave=f["clave"], nombre=f["nombre"], conteo=f["n"],
            porcentaje=Decimal(f["n"]) / Decimal(total),
        )
        for f in filas
    ]


def _realizadas(unidad: UnidadNegocio, anio: int, mes: int):
    return Atencion.objects.filter(
        unidad_negocio=unidad, anio=anio, mes=mes, estado=ESTADO_REALIZADA
    )


def mezcla_servicios(unidad: UnidadNegocio, anio: int, mes: int) -> list[ItemMezcla]:
    """% de cada servicio (código CUPS) dentro de las atenciones realizadas
    de la unidad en ese mes, de mayor a menor."""
    qs = (
        _realizadas(unidad, anio, mes)
        .values("codigo_servicio", "nombre_servicio")
        .annotate(n=Count("id"))
        .order_by("-n", "codigo_servicio")
    )
    filas = [
        {"clave": f["codigo_servicio"], "nombre": f["nombre_servicio"], "n": f["n"]}
        for f in qs
    ]
    return _con_porcentajes(filas, sum(f["n"] for f in filas))


def mezcla_servicios_agrupada(unidad: UnidadNegocio, anio: int, mes: int) -> list[ItemMezcla]:
    """% de cada GRUPO de servicio (ej. 'Espirometría pre y post' = CUPS base
    + variantes /PROGRAMAS e /INVESTIGACIÓN) en las atenciones realizadas.

    Los códigos sin asignar caen al grupo residual (es_otras) si existe; si no,
    aparecen como '(sin agrupar)' para hacerlos visibles. Orden: el de la tabla
    de grupos (GrupoServicio.orden)."""
    grupos = list(
        GrupoServicio.objects.filter(unidad_negocio=unidad).prefetch_related("codigos")
    )
    por_codigo: dict[str, GrupoServicio] = {
        c.codigo: g for g in grupos for c in g.codigos.all()
    }
    residual = next((g for g in grupos if g.es_otras), None)

    conteos: dict[str, int] = {}
    total = 0
    qs = (
        _realizadas(unidad, anio, mes)
        .values("codigo_servicio")
        .annotate(n=Count("id"))
    )
    for f in qs:
        grupo = por_codigo.get(f["codigo_servicio"], residual)
        nombre = grupo.nombre if grupo else "(sin agrupar)"
        conteos[nombre] = conteos.get(nombre, 0) + f["n"]
        total += f["n"]

    orden = {g.nombre: g.orden for g in grupos}
    filas = sorted(
        ({"clave": nombre, "nombre": nombre, "n": n} for nombre, n in conteos.items()),
        key=lambda f: (orden.get(f["nombre"], 999), f["nombre"]),
    )
    return _con_porcentajes(filas, total)


def mezcla_entidades(
    unidad: UnidadNegocio, anio: int, mes: int, codigo_servicio: str | None = None
) -> list[ItemMezcla]:
    """% de cada entidad dentro de las atenciones realizadas (opcionalmente
    de un solo servicio), de mayor a menor. Todas las entidades, sin 'otras'."""
    qs = _realizadas(unidad, anio, mes)
    if codigo_servicio:
        qs = qs.filter(codigo_servicio=codigo_servicio)
    qs = (
        qs.values("entidad__id", "entidad__nombre")
        .annotate(n=Count("id"))
        .order_by("-n", "entidad__nombre")
    )
    filas = [
        {"clave": str(f["entidad__id"] or ""), "nombre": f["entidad__nombre"] or "(sin entidad)", "n": f["n"]}
        for f in qs
    ]
    return _con_porcentajes(filas, sum(f["n"] for f in filas))
