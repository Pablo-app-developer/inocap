"""
Motor "capacidad en $": convierte la capacidad ajustada del mes en dinero.

Cadena (validada al centavo contra el Excel del usuario):
    capacidad_ajustada (app capacidad, unidad+mes)
  × % de cada celda (código de servicio, entidad) en las atenciones
    REALIZADAS ('Salida') del MISMO mes
  × tarifa de convenio de esa entidad para ese servicio
  = valor proyectado.  Las citas NO se redondean (fracciones, como el Excel).

Resolución de tarifa por celda (entidad, código), en orden:
  1. Tarifa directa (entidad, código).
  2. Tarifa de la misma entidad en OTRO código del mismo grupo — cubre las
     variantes internas '/PROGRAMAS' (CPI_*) que no existen en convenios
     pero equivalen al CUPS base.
  3. Tarifa promedio del código (o del grupo) entre las entidades que sí
     tienen convenio — el "Tarifa Promedio" del Excel para entidades sin
     convenio.
  4. $0, marcada como "sin tarifa" (visible para depurar convenios faltantes).

El resultado se agrega por GrupoServicio para presentarlo como las tablas
del Excel (grupo → detalle por entidad), pero el cálculo es por celda.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from django.db.models import Count

from apps.capacidad.services import orm as capacidad_orm
from apps.core.models import UnidadNegocio

from ..models import ESTADO_REALIZADA, Atencion, GrupoServicio, TarifaConvenio

CERO = Decimal("0")


@dataclass
class LineaEntidad:
    entidad: str
    conteo_real: int
    pct: Decimal              # fracción dentro del grupo
    citas: Decimal            # proyectadas (sin redondear)
    tarifa_promedio: Decimal  # tarifa efectiva (valor/citas), informativa
    valor: Decimal
    con_fallback: bool = False   # usó tarifa promedio (no convenio directo)
    sin_tarifa: bool = False     # ninguna tarifa disponible → $0


@dataclass
class LineaGrupo:
    nombre: str
    orden: int
    conteo_real: int
    pct: Decimal              # fracción dentro de la unidad+mes
    citas: Decimal            # proyectadas
    valor: Decimal
    entidades: list[LineaEntidad] = field(default_factory=list)


@dataclass
class ProyeccionDinero:
    unidad: UnidadNegocio
    anio: int
    mes: int
    capacidad_ajustada: int
    total_realizadas: int     # atenciones 'Salida' del mes (base de la mezcla)
    valor_total: Decimal = CERO
    grupos: list[LineaGrupo] = field(default_factory=list)
    celdas_sin_tarifa: int = 0


def _tarifas_por_celda(unidad) -> dict[tuple[int, str], Decimal]:
    """{(entidad_id, codigo): valor} de todos los convenios con valor > 0."""
    return {
        (t.entidad_id, t.codigo_servicio): t.valor
        for t in TarifaConvenio.objects.filter(valor__gt=0)
    }


def _grupos_de(unidad):
    grupos = list(
        GrupoServicio.objects.filter(unidad_negocio=unidad).prefetch_related("codigos")
    )
    por_codigo = {c.codigo: g for g in grupos for c in g.codigos.all()}
    residual = next((g for g in grupos if g.es_otras), None)
    return grupos, por_codigo, residual


def proyeccion_dinero(unidad: UnidadNegocio, anio: int, mes: int) -> ProyeccionDinero:
    capacidad = capacidad_orm.total_neto_unidad(unidad, anio, mes)

    celdas = list(
        Atencion.objects.filter(
            unidad_negocio=unidad, anio=anio, mes=mes, estado=ESTADO_REALIZADA
        )
        .values("codigo_servicio", "entidad_id", "entidad__nombre")
        .annotate(n=Count("id"))
    )
    total = sum(c["n"] for c in celdas)
    resultado = ProyeccionDinero(
        unidad=unidad, anio=anio, mes=mes,
        capacidad_ajustada=capacidad, total_realizadas=total,
    )
    if not total or not capacidad:
        return resultado

    tarifas = _tarifas_por_celda(unidad)
    grupos, grupo_por_codigo, residual = _grupos_de(unidad)

    # Promedios de respaldo: por código y por grupo (solo tarifas existentes).
    valores_por_codigo: dict[str, list[Decimal]] = {}
    for (ent_id, codigo), valor in tarifas.items():
        valores_por_codigo.setdefault(codigo, []).append(valor)
    promedio_codigo = {c: sum(v) / len(v) for c, v in valores_por_codigo.items()}

    def codigos_del_grupo(grupo):
        return [c.codigo for c in grupo.codigos.all()] if grupo else []

    def promedio_grupo(grupo) -> Decimal:
        valores = [promedio_codigo[c] for c in codigos_del_grupo(grupo) if c in promedio_codigo]
        return sum(valores) / len(valores) if valores else CERO

    def tarifa_para(entidad_id, codigo, grupo) -> tuple[Decimal, bool, bool]:
        """(tarifa, con_fallback, sin_tarifa) según la cadena de resolución."""
        if entidad_id is not None:
            directa = tarifas.get((entidad_id, codigo))
            if directa is not None:
                return directa, False, False
            # mismo grupo, otro código (variantes internas tipo CPI_*)
            for otro in codigos_del_grupo(grupo):
                valor = tarifas.get((entidad_id, otro))
                if valor is not None:
                    return valor, False, False
        prom = promedio_codigo.get(codigo) or promedio_grupo(grupo)
        if prom:
            return prom, True, False
        return CERO, False, True

    # Acumular por (grupo, entidad).
    acumulado: dict[tuple[str, str], dict] = {}
    conteo_grupos: dict[str, dict] = {}
    cap = Decimal(capacidad)
    tot = Decimal(total)

    for celda in celdas:
        codigo = celda["codigo_servicio"]
        grupo = grupo_por_codigo.get(codigo, residual)
        nombre_grupo = grupo.nombre if grupo else "(sin agrupar)"
        orden_grupo = grupo.orden if grupo else 999
        entidad_nombre = celda["entidad__nombre"] or "(sin entidad)"

        citas = cap * Decimal(celda["n"]) / tot
        tarifa, con_fallback, sin_tarifa = tarifa_para(celda["entidad_id"], codigo, grupo)
        valor = citas * tarifa
        if sin_tarifa:
            resultado.celdas_sin_tarifa += 1

        g = conteo_grupos.setdefault(nombre_grupo, {"orden": orden_grupo, "n": 0})
        g["n"] += celda["n"]

        e = acumulado.setdefault((nombre_grupo, entidad_nombre), {
            "n": 0, "citas": CERO, "valor": CERO, "con_fallback": False, "sin_tarifa": False,
        })
        e["n"] += celda["n"]
        e["citas"] += citas
        e["valor"] += valor
        e["con_fallback"] = e["con_fallback"] or con_fallback
        e["sin_tarifa"] = e["sin_tarifa"] or sin_tarifa

    for nombre_grupo, datos in sorted(conteo_grupos.items(), key=lambda kv: (kv[1]["orden"], kv[0])):
        linea = LineaGrupo(
            nombre=nombre_grupo, orden=datos["orden"], conteo_real=datos["n"],
            pct=Decimal(datos["n"]) / tot,
            citas=cap * Decimal(datos["n"]) / tot,
            valor=CERO,
        )
        entidades = [
            (ent, e) for (g, ent), e in acumulado.items() if g == nombre_grupo
        ]
        for ent, e in sorted(entidades, key=lambda kv: -kv[1]["n"]):
            linea.entidades.append(LineaEntidad(
                entidad=ent, conteo_real=e["n"],
                pct=Decimal(e["n"]) / Decimal(datos["n"]),
                citas=e["citas"],
                tarifa_promedio=(e["valor"] / e["citas"]) if e["citas"] else CERO,
                valor=e["valor"],
                con_fallback=e["con_fallback"], sin_tarifa=e["sin_tarifa"],
            ))
            linea.valor += e["valor"]
        resultado.grupos.append(linea)
        resultado.valor_total += linea.valor

    return resultado
