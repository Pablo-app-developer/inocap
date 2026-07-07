"""
Motor de cálculo de capacidad instalada — FUNCIONES PURAS.

No dependen de Django ni de la BD: reciben dataclasses de entrada y devuelven
resultados. Así las pruebas validan las fórmulas de forma aislada.

Reglas replicadas del Excel (con la corrección acordada del NETO):

  citas/día         = ROUND_HALF_UP(horas_día / tiempo_estándar)      [REDONDEAR de Excel]

  Método POR_HORAS / PERSONALIZADO
    EXCEL_LEGACY:  citas_mes = (cd_lav·dias_lav + cd_sab·sabados + Σ términos_semana)·semanas
                               + Σ términos_mes
    CALENDARIO:    citas_mes = cd_lav·dias_lav_real + cd_sab·sabados_real
                               + Σ términos_semana·semanas + Σ términos_mes
       (dias_lav_real / sabados_real = conteo real del mes descontando festivos)

  Método POR_DIA_SEMANA (sedes municipales)
    EXCEL_LEGACY:  citas_mes = (Σ dias·citas_día  de patrones L–V)·semanas + Σ sábados_mes
    CALENDARIO:    citas_mes =  Σ ocurrencias_reales·citas_día        + Σ sábados_mes

  citas_mes_total = citas_mes + ajuste_sobreatención            (columna J)
  NETO            = citas_mes_total − Σ novedades_descontar + Σ novedades_sumar
                    (⚠ DIFERENCIA INTENCIONAL vs Excel: el Excel usaba citas_mes (H),
                     ignorando el ajuste por sobreatención; aquí sí lo incluimos.)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Sequence

# Constantes de modo (evita importar el modelo en las funciones puras).
MODO_CALENDARIO = "CALENDARIO"
MODO_EXCEL_LEGACY = "EXCEL_LEGACY"

PERIODICIDAD_SEMANAL = "SEMANAL"
PERIODICIDAD_MENSUAL = "MENSUAL"

SIGNO_DESCONTAR = "DESCONTAR"
SIGNO_SUMAR = "SUMAR"


# --------------------------------------------------------------------------- #
# Entradas
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class DiasMes:
    """Días del mes que alimentan el cálculo.

    En modo CALENDARIO: dias_lav/sabados = conteo real del mes (ya totales).
    En modo EXCEL_LEGACY: dias_lav/sabados = valores por semana (5 y 1).
    `semanas` es el multiplicador de la base semanal / términos semanales.
    """

    dias_lav: int
    sabados: int
    semanas: int


@dataclass(frozen=True)
class Termino:
    citas: int
    periodicidad: str = PERIODICIDAD_SEMANAL


@dataclass(frozen=True)
class Novedad:
    citas: int
    signo: str = SIGNO_DESCONTAR


@dataclass(frozen=True)
class ResultadoCapacidad:
    citas_dia_lav: int
    citas_dia_sabado: int
    citas_mes: int
    citas_mes_total: int
    neto: int


# --------------------------------------------------------------------------- #
# Primitivas
# --------------------------------------------------------------------------- #
def round_half_up(valor) -> int:
    """Redondeo 'mitad hacia arriba' como REDONDEAR de Excel (no banker's)."""
    return int(Decimal(str(valor)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def citas_por_dia(horas_dia, tiempo_estandar_horas) -> int:
    """ROUND_HALF_UP(horas_día / tiempo_estándar). 0 si el tiempo estándar es 0."""
    te = Decimal(str(tiempo_estandar_horas))
    if te <= 0:
        return 0
    return round_half_up(Decimal(str(horas_dia)) / te)


# --------------------------------------------------------------------------- #
# Citas mes por método
# --------------------------------------------------------------------------- #
def citas_mes_por_horas(
    *,
    citas_dia_lav: int,
    citas_dia_sabado: int,
    dias: DiasMes,
    terminos: Sequence[Termino] = (),
    modo: str = MODO_CALENDARIO,
) -> int:
    sem = sum(t.citas for t in terminos if t.periodicidad == PERIODICIDAD_SEMANAL)
    men = sum(t.citas for t in terminos if t.periodicidad == PERIODICIDAD_MENSUAL)

    if modo == MODO_EXCEL_LEGACY:
        base_semanal = citas_dia_lav * dias.dias_lav + citas_dia_sabado * dias.sabados + sem
        return base_semanal * dias.semanas + men

    # CALENDARIO: dias_lav / sabados ya son totales del mes.
    return (
        citas_dia_lav * dias.dias_lav
        + citas_dia_sabado * dias.sabados
        + sem * dias.semanas
        + men
    )


def citas_mes_por_dia(citas_dias: Sequence[int], ocurrencias_dias: Sequence[int]) -> int:
    """Método POR_DIA_SEMANA: Σ (citas del día × veces que ese día ocurre en el mes).

    citas_dias / ocurrencias_dias son tuplas de 7 (0=lun … 6=dom). Las ocurrencias
    las provee el adaptador ORM (reales del calendario, o fijas en modo legacy)."""
    return sum(c * o for c, o in zip(citas_dias, ocurrencias_dias))


# --------------------------------------------------------------------------- #
# Neto
# --------------------------------------------------------------------------- #
def calcular_neto(citas_mes: int, ajuste_sobreatencion: int, novedades: Sequence[Novedad]) -> tuple[int, int]:
    """Devuelve (citas_mes_total, neto).

    citas_mes_total = citas_mes + ajuste_sobreatención
    neto            = citas_mes_total − Σ descontar + Σ sumar
    """
    descontar = sum(n.citas for n in novedades if n.signo == SIGNO_DESCONTAR)
    sumar = sum(n.citas for n in novedades if n.signo == SIGNO_SUMAR)
    citas_mes_total = citas_mes + ajuste_sobreatencion
    neto = citas_mes_total - descontar + sumar
    return citas_mes_total, neto


# --------------------------------------------------------------------------- #
# Orquestador de una fila de capacidad
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class EntradaCapacidad:
    metodo: str  # 'POR_HORAS' | 'POR_DIA_SEMANA' | 'PERSONALIZADO'
    modo: str
    dias: DiasMes
    horas_dia_lav: Decimal = Decimal("0")
    horas_dia_sabado: Decimal = Decimal("0")
    tiempo_estandar_horas: Decimal = Decimal("0")
    ajuste_sobreatencion: int = 0
    terminos: Sequence[Termino] = field(default_factory=tuple)
    citas_dias: Sequence[int] = (0, 0, 0, 0, 0, 0, 0)
    ocurrencias_dias: Sequence[int] = (0, 0, 0, 0, 0, 0, 0)
    novedades: Sequence[Novedad] = field(default_factory=tuple)


def calcular_capacidad(entrada: EntradaCapacidad) -> ResultadoCapacidad:
    """Calcula una fila completa de capacidad para cualquier método."""
    if entrada.metodo == "POR_DIA_SEMANA":
        cd_lav = 0
        cd_sab = 0
        citas_mes = citas_mes_por_dia(entrada.citas_dias, entrada.ocurrencias_dias)
    else:  # POR_HORAS y PERSONALIZADO comparten fórmula (overrides van en `dias`/`terminos`)
        cd_lav = citas_por_dia(entrada.horas_dia_lav, entrada.tiempo_estandar_horas)
        cd_sab = citas_por_dia(entrada.horas_dia_sabado, entrada.tiempo_estandar_horas)
        citas_mes = citas_mes_por_horas(
            citas_dia_lav=cd_lav,
            citas_dia_sabado=cd_sab,
            dias=entrada.dias,
            terminos=entrada.terminos,
            modo=entrada.modo,
        )

    citas_mes_total, neto = calcular_neto(
        citas_mes, entrada.ajuste_sobreatencion, entrada.novedades
    )
    return ResultadoCapacidad(
        citas_dia_lav=cd_lav,
        citas_dia_sabado=cd_sab,
        citas_mes=citas_mes,
        citas_mes_total=citas_mes_total,
        neto=neto,
    )
