"""
Pruebas de creación de mes nuevo clonando el último mes (services.meses).
"""

from decimal import Decimal

import pytest

from apps.capacidad.models import (
    CapacidadSala,
    ModoCalculo,
    Novedad,
    ParametroMensual,
    Signo,
    TerminoAdicional,
)
from apps.capacidad.services import meses
from apps.core.models import MetodoCalculo, Sala, Sede, UnidadNegocio


@pytest.fixture
def unidad(db):
    return UnidadNegocio.objects.create(nombre="Laboratorio Pulmonar", codigo="lab-pulmonar")


@pytest.fixture
def sede(db):
    return Sede.objects.create(nombre="Cabecera", codigo="cabecera")


@pytest.fixture
def enero(unidad, sede):
    """Enero con una sala POR_HORAS (con novedad y ajuste) y una POR_DIA_SEMANA."""
    param = ParametroMensual.objects.create(
        unidad_negocio=unidad, anio=2026, mes=1, modo=ModoCalculo.EXCEL_LEGACY,
        dias_lav=5, sabados_semana=1, semanas_mes=4,
    )
    s1 = Sala.objects.create(
        unidad_negocio=unidad, sede=sede, nombre="Cabecera 1",
        metodo_calculo=MetodoCalculo.POR_HORAS,
    )
    c1 = CapacidadSala.objects.create(
        sala=s1, parametro=param,
        horas_dia_lav=Decimal("10.5"), horas_dia_sabado=Decimal("10.5"),
        tiempo_estandar_horas=Decimal("0.5"), ajuste_sobreatencion=3,
        observaciones="nota de enero",
    )
    Novedad.objects.create(capacidad_sala=c1, citas_afectadas=2, signo=Signo.DESCONTAR)
    TerminoAdicional.objects.create(capacidad_sala=c1, citas=18, descripcion="extra")

    s2 = Sala.objects.create(
        unidad_negocio=unidad, sede=sede, nombre="Barranca",
        metodo_calculo=MetodoCalculo.POR_DIA_SEMANA, atiende_sabados=False,
    )
    CapacidadSala.objects.create(
        sala=s2, parametro=param, tiempo_estandar_horas=Decimal("0.5"),
        citas_lun=16, citas_mar=8, citas_mie=16, citas_jue=17, citas_vie=16,
    )
    return param


@pytest.mark.django_db
def test_siguiente_periodo(enero, unidad):
    assert meses.siguiente_periodo(unidad) == (2026, 2)


@pytest.mark.django_db
def test_siguiente_periodo_diciembre(enero, unidad):
    enero.mes = 12
    enero.save()
    assert meses.siguiente_periodo(unidad) == (2027, 1)


@pytest.mark.django_db
def test_crear_mes_clona_entradas_sin_novedades(enero, unidad):
    nuevo = meses.crear_mes(unidad, 2026, 2)

    assert nuevo.modo == enero.modo
    assert nuevo.capacidades.count() == 2

    c1 = nuevo.capacidades.get(sala__nombre="Cabecera 1")
    assert c1.horas_dia_lav == Decimal("10.50")
    assert c1.tiempo_estandar_horas == Decimal("0.500")
    # Lo específico del mes NO se copia:
    assert c1.ajuste_sobreatencion == 0
    assert c1.observaciones == ""
    assert c1.novedades.count() == 0
    # Los términos estructurales sí:
    assert list(c1.terminos.values_list("citas", flat=True)) == [18]
    # Snapshot recalculado (no en cero):
    assert c1.citas_mes > 0

    c2 = nuevo.capacidades.get(sala__nombre="Barranca")
    assert c2.citas_por_dia_semana == (16, 8, 16, 17, 16, 0, 0)
    assert c2.citas_mes > 0


@pytest.mark.django_db
def test_crear_mes_existente_falla(enero, unidad):
    with pytest.raises(ValueError):
        meses.crear_mes(unidad, 2026, 1)


@pytest.mark.django_db
def test_crear_mes_respeta_salas_activas(enero, unidad, sede):
    # Sala desactivada no entra; sala nueva entra en cero.
    Sala.objects.filter(nombre="Barranca").update(activo=False)
    Sala.objects.create(
        unidad_negocio=unidad, sede=sede, nombre="Sala nueva",
        metodo_calculo=MetodoCalculo.POR_HORAS,
    )

    nuevo = meses.crear_mes(unidad, 2026, 2)

    nombres = set(nuevo.capacidades.values_list("sala__nombre", flat=True))
    assert nombres == {"Cabecera 1", "Sala nueva"}
    assert nuevo.capacidades.get(sala__nombre="Sala nueva").citas_mes == 0
