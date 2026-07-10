"""
Pruebas de las mezclas de servicios y entidades: solo estado 'Salida',
mismo mes, todas las entidades.
"""

import datetime
from decimal import Decimal

import pytest

from apps.atenciones import selectors
from apps.atenciones.models import Atencion, Entidad
from apps.core.models import UnidadNegocio


@pytest.fixture
def unidad(db):
    return UnidadNegocio.objects.create(nombre="Laboratorio Pulmonar", codigo="lab-pulmonar")


def _atencion(unidad, dia, codigo, nombre, estado, entidad):
    return Atencion.objects.create(
        fecha=datetime.date(2026, 1, dia), codigo_servicio=codigo,
        nombre_servicio=nombre, estado=estado, entidad=entidad, unidad_negocio=unidad,
    )


@pytest.fixture
def datos(unidad):
    sanitas = Entidad.objects.create(nombre="SANITAS EPS SA")
    sura = Entidad.objects.create(nombre="SURA EPS")
    # Enero: 3 espirometrías Salida (2 Sanitas, 1 Sura), 1 FeNO Salida (Sura),
    # 1 espirometría Cancelada (no cuenta), y 1 espirometría de FEBRERO (no cuenta).
    _atencion(unidad, 5, "893801", "ESPIROMETRIA", "Salida", sanitas)
    _atencion(unidad, 6, "893801", "ESPIROMETRIA", "Salida", sanitas)
    _atencion(unidad, 7, "893801", "ESPIROMETRIA", "Salida", sura)
    _atencion(unidad, 8, "875101", "FENO", "Salida", sura)
    _atencion(unidad, 9, "893801", "ESPIROMETRIA", "Cancelada", sanitas)
    Atencion.objects.create(
        fecha=datetime.date(2026, 2, 2), codigo_servicio="893801",
        nombre_servicio="ESPIROMETRIA", estado="Salida", entidad=sanitas,
        unidad_negocio=unidad,
    )
    return sanitas, sura


@pytest.mark.django_db
def test_mezcla_servicios_solo_salida_y_mismo_mes(unidad, datos):
    mezcla = selectors.mezcla_servicios(unidad, 2026, 1)

    assert [(m.clave, m.conteo) for m in mezcla] == [("893801", 3), ("875101", 1)]
    assert mezcla[0].porcentaje == Decimal(3) / Decimal(4)
    assert sum(m.porcentaje for m in mezcla) == 1


@pytest.mark.django_db
def test_mezcla_entidades_por_servicio(unidad, datos):
    sanitas, sura = datos
    mezcla = selectors.mezcla_entidades(unidad, 2026, 1, codigo_servicio="893801")

    assert [(m.nombre, m.conteo) for m in mezcla] == [("SANITAS EPS SA", 2), ("SURA EPS", 1)]
    assert mezcla[0].porcentaje == Decimal(2) / Decimal(3)


@pytest.mark.django_db
def test_mezcla_entidades_toda_la_unidad(unidad, datos):
    mezcla = selectors.mezcla_entidades(unidad, 2026, 1)
    assert [(m.nombre, m.conteo) for m in mezcla] == [("SANITAS EPS SA", 2), ("SURA EPS", 2)]


@pytest.mark.django_db
def test_mes_sin_datos_devuelve_vacio(unidad):
    assert selectors.mezcla_servicios(unidad, 2026, 3) == []


@pytest.mark.django_db
def test_mezcla_agrupada_fusiona_variantes_y_residual(unidad, datos):
    """El CUPS base y su variante /PROGRAMAS caen al mismo grupo; un código
    sin asignar cae al grupo residual (es_otras)."""
    from apps.atenciones.models import CodigoServicioGrupo, GrupoServicio

    espiro = GrupoServicio.objects.create(unidad_negocio=unidad, nombre="Espirometría pre y post", orden=0)
    CodigoServicioGrupo.objects.create(grupo=espiro, codigo="893801")
    CodigoServicioGrupo.objects.create(grupo=espiro, codigo="CPI_15")
    otras = GrupoServicio.objects.create(unidad_negocio=unidad, nombre="Otras pruebas", orden=1, es_otras=True)

    sanitas, _ = datos
    # variante /PROGRAMAS del mismo servicio + un código no asignado
    _atencion(unidad, 10, "CPI_15", "ESPIROMETRIA / PROGRAMAS", "Salida", sanitas)
    _atencion(unidad, 11, "999999", "PRUEBA RARA", "Salida", sanitas)

    mezcla = selectors.mezcla_servicios_agrupada(unidad, 2026, 1)

    # 3 espirometrías CUPS + 1 CPI = 4 juntas; FENO (875101) sin asignar → Otras; 999999 → Otras
    assert [(m.nombre, m.conteo) for m in mezcla] == [
        ("Espirometría pre y post", 4),
        ("Otras pruebas", 2),
    ]
    assert sum(m.porcentaje for m in mezcla) == 1
