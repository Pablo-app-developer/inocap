"""
Pruebas de integración: adaptador ORM + persistencia del snapshot.
Requiere BD (pytest.mark.django_db).
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.calendario.models import Festivo
from apps.capacidad.models import (
    CapacidadSala,
    ModoCalculo,
    Novedad,
    ParametroMensual,
    Signo,
    TerminoAdicional,
)
from apps.capacidad.services import orm
from apps.core.models import MetodoCalculo, Sala, Sede, UnidadNegocio


@pytest.fixture
def unidad(db):
    return UnidadNegocio.objects.create(nombre="Laboratorio Pulmonar", codigo="lab-pulmonar")


@pytest.fixture
def sede(db):
    return Sede.objects.create(nombre="Cabecera", codigo="cabecera")


def _param(unidad, modo=ModoCalculo.EXCEL_LEGACY):
    return ParametroMensual.objects.create(
        unidad_negocio=unidad, anio=2026, mes=1, modo=modo,
        dias_lav=5, sabados_semana=1, semanas_mes=4,
        minutos_hora=60, tiempo_por_cita_min=30,
    )


@pytest.mark.django_db
def test_recalcular_cabecera1(unidad, sede):
    param = _param(unidad)
    sala = Sala.objects.create(
        unidad_negocio=unidad, sede=sede, nombre="Cabecera 1",
        metodo_calculo=MetodoCalculo.POR_HORAS,
    )
    cap = CapacidadSala.objects.create(
        sala=sala, parametro=param,
        horas_dia_lav=Decimal("10.5"), horas_dia_sabado=Decimal("10.5"),
        tiempo_estandar_horas=Decimal("0.5"),
    )
    Novedad.objects.create(capacidad_sala=cap, citas_afectadas=2, signo=Signo.DESCONTAR)

    r = orm.recalcular(cap)

    assert r.citas_dia_lav == 21
    assert r.citas_mes == 504
    assert r.neto == 502
    cap.refresh_from_db()
    assert cap.neto_capacidad_ajustada == 502  # snapshot persistido


@pytest.mark.django_db
def test_recalcular_cardiopulmonar(unidad, sede):
    param = _param(unidad)
    sala = Sala.objects.create(
        unidad_negocio=unidad, sede=sede, nombre="Cardiopulmonar",
        metodo_calculo=MetodoCalculo.PERSONALIZADO,
    )
    cap = CapacidadSala.objects.create(
        sala=sala, parametro=param,
        horas_dia_lav=Decimal("10.5"), horas_dia_sabado=Decimal("10.5"),
        tiempo_estandar_horas=Decimal("0.5"),
        override_dias_lav=3, override_sabados=0,
    )
    TerminoAdicional.objects.create(capacidad_sala=cap, citas=30, descripcion="15×2")
    TerminoAdicional.objects.create(capacidad_sala=cap, citas=18, descripcion="+18")

    r = orm.recalcular(cap)
    assert r.citas_mes == 444


@pytest.mark.django_db
def test_personalizado_es_semanal_aun_en_calendario(unidad, sede):
    """PERSONALIZADO usa receta semanal (× semanas) incluso si la unidad está
    en modo CALENDARIO: Cardiopulmonar debe seguir dando 444, no verse afectado
    por los días reales del mes ni por los festivos."""
    from datetime import date

    from apps.calendario.models import Festivo

    Festivo.objects.create(fecha=date(2026, 1, 1), nombre="Año Nuevo")
    Festivo.objects.create(fecha=date(2026, 1, 12), nombre="Reyes")
    param = _param(unidad, modo=ModoCalculo.CALENDARIO)
    sala = Sala.objects.create(
        unidad_negocio=unidad, sede=sede, nombre="Cardiopulmonar",
        metodo_calculo=MetodoCalculo.PERSONALIZADO,
    )
    cap = CapacidadSala.objects.create(
        sala=sala, parametro=param,
        horas_dia_lav=Decimal("10.5"), horas_dia_sabado=Decimal("10.5"),
        tiempo_estandar_horas=Decimal("0.5"),
        override_dias_lav=3, override_sabados=0,
    )
    TerminoAdicional.objects.create(capacidad_sala=cap, citas=30)
    TerminoAdicional.objects.create(capacidad_sala=cap, citas=18)

    r = orm.recalcular(cap)
    assert r.citas_mes == 444


@pytest.mark.django_db
def test_por_horas_calendario_cuenta_quinto_sabado(unidad, sede):
    """POR_HORAS en CALENDARIO cuenta el 5.º sábado de enero: 504 -> 525."""
    from datetime import date

    from apps.calendario.models import Festivo

    Festivo.objects.create(fecha=date(2026, 1, 1), nombre="Año Nuevo")
    Festivo.objects.create(fecha=date(2026, 1, 12), nombre="Reyes")
    param = _param(unidad, modo=ModoCalculo.CALENDARIO)
    sala = Sala.objects.create(
        unidad_negocio=unidad, sede=sede, nombre="Cabecera 1",
        metodo_calculo=MetodoCalculo.POR_HORAS,
    )
    cap = CapacidadSala.objects.create(
        sala=sala, parametro=param,
        horas_dia_lav=Decimal("10.5"), horas_dia_sabado=Decimal("10.5"),
        tiempo_estandar_horas=Decimal("0.5"),
    )
    r = orm.recalcular(cap)
    # 21 × 20 días L–V (22 − 2 festivos) + 21 × 5 sábados = 420 + 105 = 525
    assert r.citas_mes == 525


@pytest.mark.django_db
def test_recalcular_barranca_dia_semana(unidad):
    """Barranca por día de la semana en modo LEGACY (4 ocurrencias c/u): 73×4=292."""
    sede_barranca = Sede.objects.create(nombre="Barranca", codigo="barranca", es_municipal=True)
    param = _param(unidad)  # EXCEL_LEGACY -> cada día L–V ocurre semanas_mes (4) veces
    sala = Sala.objects.create(
        unidad_negocio=unidad, sede=sede_barranca, nombre="Barranca",
        metodo_calculo=MetodoCalculo.POR_DIA_SEMANA, atiende_sabados=False,
    )
    cap = CapacidadSala.objects.create(
        sala=sala, parametro=param, tiempo_estandar_horas=Decimal("0.5"),
        citas_lun=16, citas_mar=8, citas_mie=16, citas_jue=17, citas_vie=16,
    )
    Novedad.objects.create(capacidad_sala=cap, citas_afectadas=8, signo=Signo.DESCONTAR)
    Novedad.objects.create(capacidad_sala=cap, citas_afectadas=17, signo=Signo.DESCONTAR)

    r = orm.recalcular(cap)
    assert r.citas_mes == 292  # 73 × 4
    assert r.neto == 267


@pytest.mark.django_db
def test_barranca_calendario_cuenta_dias_reales(unidad):
    """En CALENDARIO, Barranca cuenta las ocurrencias reales de enero 2026 (=292)."""
    from datetime import date

    from apps.calendario.models import Festivo

    Festivo.objects.create(fecha=date(2026, 1, 1), nombre="Año Nuevo")
    Festivo.objects.create(fecha=date(2026, 1, 12), nombre="Reyes")
    sede_b = Sede.objects.create(nombre="Barranca", codigo="barranca", es_municipal=True)
    param = _param(unidad, modo=ModoCalculo.CALENDARIO)
    sala = Sala.objects.create(
        unidad_negocio=unidad, sede=sede_b, nombre="Barranca",
        metodo_calculo=MetodoCalculo.POR_DIA_SEMANA, atiende_sabados=False,
    )
    cap = CapacidadSala.objects.create(
        sala=sala, parametro=param,
        citas_lun=16, citas_mar=8, citas_mie=16, citas_jue=17, citas_vie=16,
    )
    r = orm.recalcular(cap)
    # Lun3×16 + Mar4×8 + Mié4×16 + Jue4×17 + Vie5×16 = 48+32+64+68+80 = 292
    assert r.citas_mes == 292


@pytest.mark.django_db
def test_modo_calendario_usa_festivos(unidad, sede):
    """En modo CALENDARIO, un festivo entre semana reduce las citas mes."""
    Festivo.objects.create(fecha=date(2026, 1, 1), nombre="Año Nuevo")
    Festivo.objects.create(fecha=date(2026, 1, 12), nombre="Reyes")
    param = _param(unidad, modo=ModoCalculo.CALENDARIO)
    sala = Sala.objects.create(
        unidad_negocio=unidad, sede=sede, nombre="Cabecera 1",
        metodo_calculo=MetodoCalculo.POR_HORAS, atiende_sabados=False,
    )
    cap = CapacidadSala.objects.create(
        sala=sala, parametro=param,
        horas_dia_lav=Decimal("10.5"), tiempo_estandar_horas=Decimal("0.5"),
    )
    r = orm.recalcular(cap)
    # 21 citas/día × 20 días L–V hábiles (22 − 2 festivos) = 420
    assert r.citas_mes == 420


@pytest.mark.django_db
def test_total_neto_unidad(unidad, sede):
    param = _param(unidad)
    for nombre in ("Cabecera 1", "Cabecera 2"):
        sala = Sala.objects.create(unidad_negocio=unidad, sede=sede, nombre=nombre)
        cap = CapacidadSala.objects.create(
            sala=sala, parametro=param,
            horas_dia_lav=Decimal("10.5"), horas_dia_sabado=Decimal("10.5"),
            tiempo_estandar_horas=Decimal("0.5"),
        )
        orm.recalcular(cap)
    total = orm.total_neto_unidad(unidad, 2026, 1)
    assert total == 1008  # 504 × 2


@pytest.mark.django_db
def test_sabados_alternos_legacy_cuenta_mitad(unidad):
    """Malaga: 7 citas un sabado de por medio. LEGACY: 4 sabados -> cuenta 2."""
    sede_m = Sede.objects.create(nombre="Malaga", codigo="malaga", es_municipal=True)
    param = _param(unidad)  # EXCEL_LEGACY, semanas_mes=4
    sala = Sala.objects.create(
        unidad_negocio=unidad, sede=sede_m, nombre="Malaga",
        metodo_calculo=MetodoCalculo.POR_DIA_SEMANA, atiende_sabados=True,
    )
    cap = CapacidadSala.objects.create(
        sala=sala, parametro=param,
        citas_lun=16, citas_mar=16, citas_mie=16, citas_jue=16, citas_vie=15,
        citas_sab=7, sabados_alternos=True,
    )
    r = orm.recalcular(cap)
    # (16+16+16+16+15) x 4 + 7 x (4 // 2) = 316 + 14 = 330
    assert r.citas_mes == 330


@pytest.mark.django_db
def test_sabados_alternos_calendario_mitad_piso(unidad):
    """CALENDARIO enero 2026: 5 sabados reales -> alternos cuenta 5 // 2 = 2."""
    from datetime import date

    Festivo.objects.create(fecha=date(2026, 1, 1), nombre="Anio Nuevo")
    Festivo.objects.create(fecha=date(2026, 1, 12), nombre="Reyes")
    sede_m = Sede.objects.create(nombre="Malaga", codigo="malaga", es_municipal=True)
    param = _param(unidad, modo=ModoCalculo.CALENDARIO)
    sala = Sala.objects.create(
        unidad_negocio=unidad, sede=sede_m, nombre="Malaga",
        metodo_calculo=MetodoCalculo.POR_DIA_SEMANA, atiende_sabados=True,
    )
    cap = CapacidadSala.objects.create(
        sala=sala, parametro=param,
        citas_lun=16, citas_mar=16, citas_mie=16, citas_jue=16, citas_vie=15,
        citas_sab=7, sabados_alternos=True,
    )
    r = orm.recalcular(cap)
    # Lun3x16 + Mar4x16 + Mie4x16 + Jue4x16 + Vie5x15 + Sab(5//2=2)x7
    # = 48 + 64 + 64 + 64 + 75 + 14 = 329
    assert r.citas_mes == 329
