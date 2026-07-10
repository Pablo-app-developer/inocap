"""
Pruebas del motor "capacidad en $": proyección, resolución de tarifas
(directa, por grupo para variantes CPI_*, promedio) y citas fraccionarias.
"""

import datetime
from decimal import Decimal

import pytest

from apps.atenciones.models import (
    Atencion,
    CodigoServicioGrupo,
    Entidad,
    GrupoServicio,
    TarifaConvenio,
)
from apps.atenciones.services.dinero import proyeccion_dinero
from apps.capacidad.models import CapacidadSala, ModoCalculo, ParametroMensual
from apps.core.models import MetodoCalculo, Sala, Sede, UnidadNegocio


@pytest.fixture
def unidad(db):
    return UnidadNegocio.objects.create(nombre="Laboratorio Pulmonar", codigo="lab-pulmonar")


@pytest.fixture
def capacidad_100(unidad):
    """Capacidad ajustada del mes = 100 (POR_DIA_SEMANA legacy: 25×4 semanas)."""
    sede = Sede.objects.create(nombre="Cabecera", codigo="cabecera")
    param = ParametroMensual.objects.create(
        unidad_negocio=unidad, anio=2026, mes=1, modo=ModoCalculo.EXCEL_LEGACY, semanas_mes=4,
    )
    sala = Sala.objects.create(
        unidad_negocio=unidad, sede=sede, nombre="Sala X",
        metodo_calculo=MetodoCalculo.POR_DIA_SEMANA, atiende_sabados=False,
    )
    cap = CapacidadSala.objects.create(sala=sala, parametro=param, citas_lun=25)
    from apps.capacidad.services import orm
    orm.recalcular(cap)
    assert cap.citas_mes == 100
    return cap


@pytest.fixture
def escenario(unidad, capacidad_100):
    """80 espirometrías (60 CUPS Sanitas, 20 CPI_15 Sanitas) + 20 FeNO Sura.
    Tarifas: Sanitas 893805 = $1.000. FeNO sin convenio de Sura, pero
    Ecopetrol tiene 893819 = $500 (para el promedio)."""
    sanitas = Entidad.objects.create(nombre="SANITAS")
    sura = Entidad.objects.create(nombre="SURA")
    ecopetrol = Entidad.objects.create(nombre="ECOPETROL")

    espiro = GrupoServicio.objects.create(unidad_negocio=unidad, nombre="Espirometría", orden=0)
    CodigoServicioGrupo.objects.create(grupo=espiro, codigo="893805")
    CodigoServicioGrupo.objects.create(grupo=espiro, codigo="CPI_15")
    feno = GrupoServicio.objects.create(unidad_negocio=unidad, nombre="FeNO", orden=1)
    CodigoServicioGrupo.objects.create(grupo=feno, codigo="893819")

    TarifaConvenio.objects.create(entidad=sanitas, codigo_servicio="893805", valor=1000)
    TarifaConvenio.objects.create(entidad=ecopetrol, codigo_servicio="893819", valor=500)

    def lote(n, codigo, entidad):
        Atencion.objects.bulk_create([
            Atencion(fecha=datetime.date(2026, 1, 10), anio=2026, mes=1,
                     codigo_servicio=codigo, estado="Salida",
                     entidad=entidad, unidad_negocio=unidad)
            for _ in range(n)
        ])

    lote(60, "893805", sanitas)
    lote(20, "CPI_15", sanitas)   # variante sin tarifa propia → usa la del grupo
    lote(20, "893819", sura)      # Sura sin convenio → tarifa promedio (500)
    return sanitas, sura


@pytest.mark.django_db
def test_proyeccion_completa(unidad, escenario):
    p = proyeccion_dinero(unidad, 2026, 1)

    assert p.capacidad_ajustada == 100
    assert p.total_realizadas == 100
    assert [g.nombre for g in p.grupos] == ["Espirometría", "FeNO"]

    espiro = p.grupos[0]
    assert espiro.pct == Decimal("0.8")
    assert espiro.citas == Decimal("80")
    # 60 citas CUPS × $1000 + 20 citas CPI (tarifa del grupo $1000) = $80.000
    assert espiro.valor == Decimal("80000")
    assert espiro.entidades[0].entidad == "SANITAS"
    assert espiro.entidades[0].con_fallback is False

    feno = p.grupos[1]
    assert feno.citas == Decimal("20")
    # Sura sin convenio → promedio del código 893819 = $500 → 20 × 500 = $10.000
    assert feno.valor == Decimal("10000")
    assert feno.entidades[0].con_fallback is True

    assert p.valor_total == Decimal("90000")
    assert p.celdas_sin_tarifa == 0


@pytest.mark.django_db
def test_citas_fraccionarias_sin_redondear(unidad, capacidad_100):
    """3 atenciones sobre capacidad 100 → 33,33… citas por celda (sin redondear)."""
    ent = Entidad.objects.create(nombre="SANITAS")
    TarifaConvenio.objects.create(entidad=ent, codigo_servicio="893805", valor=300)
    Atencion.objects.bulk_create([
        Atencion(fecha=datetime.date(2026, 1, 10), anio=2026, mes=1,
                 codigo_servicio="893805", estado="Salida",
                 entidad=ent, unidad_negocio=unidad)
        for _ in range(3)
    ])

    p = proyeccion_dinero(unidad, 2026, 1)

    # capacidad 100 × 100% = 100 citas × $300 = $30.000 exactos aunque
    # internamente las celdas sean fraccionarias
    assert p.valor_total == Decimal("30000")


@pytest.mark.django_db
def test_sin_tarifa_alguna_marca_celda(unidad, capacidad_100):
    ent = Entidad.objects.create(nombre="EPS SIN CONVENIO")
    Atencion.objects.create(
        fecha=datetime.date(2026, 1, 10), anio=2026, mes=1,
        codigo_servicio="999999", estado="Salida", entidad=ent, unidad_negocio=unidad,
    )

    p = proyeccion_dinero(unidad, 2026, 1)

    assert p.valor_total == 0
    assert p.celdas_sin_tarifa == 1


@pytest.mark.django_db
def test_mes_sin_atenciones(unidad, capacidad_100):
    p = proyeccion_dinero(unidad, 2026, 2)
    assert p.total_realizadas == 0
    assert p.grupos == []
