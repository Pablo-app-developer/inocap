"""
Pruebas del selector `vista_mensual`: orden de sedes/salas y secciones
(principales primero, municipales siempre al final).
"""

from decimal import Decimal

import pytest

from apps.capacidad import selectors
from apps.capacidad.models import CapacidadSala, ModoCalculo, ParametroMensual
from apps.core.models import MetodoCalculo, Sala, Sede, UnidadNegocio


@pytest.fixture
def unidad(db):
    return UnidadNegocio.objects.create(nombre="Laboratorio Pulmonar", codigo="lab-pulmonar")


@pytest.fixture
def escenario(db, unidad):
    """Sedes con `orden` que NO coincide con el alfabético, a propósito:
    San Gil debe listarse antes que Málaga aunque "M" < "S"."""
    cabecera = Sede.objects.create(nombre="Cabecera", codigo="cabecera", orden=0)
    fosunab = Sede.objects.create(nombre="Fosunab", codigo="fosunab", orden=1)
    barranca = Sede.objects.create(nombre="Barranca", codigo="barranca", es_municipal=True, orden=2)
    san_gil = Sede.objects.create(nombre="San Gil", codigo="san-gil", es_municipal=True, orden=3)
    malaga = Sede.objects.create(nombre="Málaga", codigo="malaga", es_municipal=True, orden=4)

    param = ParametroMensual.objects.create(
        unidad_negocio=unidad, anio=2026, mes=1, modo=ModoCalculo.EXCEL_LEGACY,
    )

    # (nombre, sede, orden) — a propósito en un orden de creación "revuelto".
    salas = [
        ("Cardiopulmonar", fosunab, 5),
        ("Cabecera 1", cabecera, 0),
        ("Málaga", malaga, 0),
        ("Oscilo", fosunab, 2),
        ("San Gil", san_gil, 0),
        ("Cabecera 2", cabecera, 1),
        ("Pletismógrafo 1", fosunab, 3),
        ("Barrancabermeja", barranca, 0),
        ("Pletismografía 2", fosunab, 4),
    ]
    for nombre, sede, orden in salas:
        sala = Sala.objects.create(
            unidad_negocio=unidad, sede=sede, nombre=nombre,
            metodo_calculo=MetodoCalculo.POR_HORAS, orden=orden,
        )
        CapacidadSala.objects.create(sala=sala, parametro=param, tiempo_estandar_horas=Decimal("0.5"))

    return param


@pytest.mark.django_db
def test_secciones_principales_antes_que_municipales(escenario, unidad):
    vm = selectors.vista_mensual(unidad, 2026, 1)

    assert [s.titulo for s in vm.secciones] == ["Sedes principales", "Sedes municipales"]


@pytest.mark.django_db
def test_orden_de_salas_dentro_de_cada_sede(escenario, unidad):
    vm = selectors.vista_mensual(unidad, 2026, 1)

    principales = vm.secciones[0]
    orden_principales = [
        cap.sala.nombre for g in principales.grupos for cap in g.filas
    ]
    assert orden_principales == [
        "Cabecera 1", "Cabecera 2",
        "Oscilo", "Pletismógrafo 1", "Pletismografía 2", "Cardiopulmonar",
    ]

    municipales = vm.secciones[1]
    orden_municipales = [
        cap.sala.nombre for g in municipales.grupos for cap in g.filas
    ]
    assert orden_municipales == ["Barrancabermeja", "San Gil", "Málaga"]
