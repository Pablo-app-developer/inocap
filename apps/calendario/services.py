"""
Servicio de calendario: conteo de días hábiles reales de un mes.

Funciones puras (no tocan la BD) + un lector que obtiene los festivos desde el
modelo `Festivo`. Esto permite testear el conteo sin base de datos.
"""

from __future__ import annotations

import calendar as _cal
from dataclasses import dataclass
from datetime import date
from typing import Iterable

# 0=lunes ... 6=domingo (convención datetime.weekday)
LUN, MAR, MIE, JUE, VIE, SAB, DOM = range(7)


@dataclass(frozen=True)
class ConteoDias:
    dias_lav: int  # días lunes-viernes hábiles (sin festivos)
    sabados: int   # sábados hábiles (sin festivos)


def contar_dias_habiles(anio: int, mes: int, festivos: Iterable[date] = ()) -> ConteoDias:
    """Cuenta días L–V y sábados del mes, descontando los festivos dados."""
    festivos_set = set(festivos)
    dias_lav = 0
    sabados = 0
    for dia in range(1, _cal.monthrange(anio, mes)[1] + 1):
        fecha = date(anio, mes, dia)
        if fecha in festivos_set:
            continue
        wd = fecha.weekday()
        if wd <= VIE:
            dias_lav += 1
        elif wd == SAB:
            sabados += 1
    return ConteoDias(dias_lav=dias_lav, sabados=sabados)


def contar_ocurrencias(
    anio: int, mes: int, dias_semana: Iterable[int], festivos: Iterable[date] = ()
) -> int:
    """Cuenta cuántas veces ocurren ciertos días de la semana en el mes (sin festivos)."""
    objetivo = set(dias_semana)
    festivos_set = set(festivos)
    total = 0
    for dia in range(1, _cal.monthrange(anio, mes)[1] + 1):
        fecha = date(anio, mes, dia)
        if fecha in festivos_set:
            continue
        if fecha.weekday() in objetivo:
            total += 1
    return total


def ocurrencias_por_dia(anio: int, mes: int, festivos: Iterable[date] = ()) -> tuple:
    """Cuántas veces cae cada día de la semana en el mes (0=lun … 6=dom),
    descontando festivos. Devuelve una tupla de 7 enteros."""
    festivos_set = set(festivos)
    conteo = [0] * 7
    for dia in range(1, _cal.monthrange(anio, mes)[1] + 1):
        fecha = date(anio, mes, dia)
        if fecha in festivos_set:
            continue
        conteo[fecha.weekday()] += 1
    return tuple(conteo)


def parse_dias_semana(csv: str) -> list[int]:
    """'0,2,4' -> [0, 2, 4]. Cadena vacía -> []."""
    if not csv:
        return []
    return [int(x) for x in csv.split(",") if x.strip() != ""]


# --- Lectores ORM (import perezoso para no acoplar las funciones puras) ---

def festivos_del_mes(anio: int, mes: int) -> list[date]:
    from .models import Festivo

    return list(
        Festivo.objects.filter(fecha__year=anio, fecha__month=mes).values_list(
            "fecha", flat=True
        )
    )


def conteo_mes(anio: int, mes: int) -> ConteoDias:
    """Conteo de días hábiles del mes leyendo los festivos de la BD."""
    return contar_dias_habiles(anio, mes, festivos_del_mes(anio, mes))
