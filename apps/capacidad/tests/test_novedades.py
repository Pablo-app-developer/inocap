"""
Pruebas del módulo de novedades: habilitación por mes, registro y recálculo.
"""

from decimal import Decimal

import pytest
from django.contrib.auth.models import User

from apps.capacidad.models import (
    CapacidadSala,
    ModoCalculo,
    Novedad,
    ParametroMensual,
)
from apps.capacidad.services import orm
from apps.core.models import MetodoCalculo, PerfilUsuario, Sala, Sede, UnidadNegocio


@pytest.fixture
def escenario(db):
    unidad = UnidadNegocio.objects.create(nombre="Laboratorio Pulmonar", codigo="lab-pulmonar")
    sede = Sede.objects.create(nombre="Cabecera", codigo="cabecera")
    param = ParametroMensual.objects.create(
        unidad_negocio=unidad, anio=2026, mes=1, modo=ModoCalculo.EXCEL_LEGACY,
        dias_lav=5, sabados_semana=1, semanas_mes=4,
    )
    sala = Sala.objects.create(
        unidad_negocio=unidad, sede=sede, nombre="Cabecera 1",
        metodo_calculo=MetodoCalculo.POR_HORAS,
    )
    cap = CapacidadSala.objects.create(
        sala=sala, parametro=param,
        horas_dia_lav=Decimal("10.5"), horas_dia_sabado=Decimal("10.5"),
        tiempo_estandar_horas=Decimal("0.5"),
    )
    orm.recalcular(cap)  # citas_mes = 504
    return unidad, param, cap


def _dar_acceso(user, unidad):
    perfil = PerfilUsuario.objects.create(usuario=user)
    perfil.unidades_negocio.add(unidad)
    return user


@pytest.fixture
def staff(db, escenario):
    unidad, _, _ = escenario
    return _dar_acceso(User.objects.create_user("jefe", password="x", is_staff=True), unidad)


@pytest.fixture
def usuario(db, escenario):
    unidad, _, _ = escenario
    return _dar_acceso(User.objects.create_user("digitador", password="x", is_staff=False), unidad)


DATOS = {"tipo": "INCAPACIDAD", "signo": "DESCONTAR", "citas_afectadas": 5}


@pytest.mark.django_db
def test_mes_cerrado_no_permite_agregar(client, escenario, usuario):
    _, param, cap = escenario
    assert param.novedades_abiertas is False
    client.force_login(usuario)

    r = client.post(f"/novedades/agregar/{cap.id}/", DATOS)

    assert r.status_code == 200
    assert "no está habilitado" in r.content.decode()
    assert cap.novedades.count() == 0


@pytest.mark.django_db
def test_mes_abierto_agrega_y_recalcula(client, escenario, usuario):
    _, param, cap = escenario
    param.novedades_abiertas = True
    param.save()
    client.force_login(usuario)

    r = client.post(f"/novedades/agregar/{cap.id}/", DATOS)

    assert r.status_code == 200
    assert cap.novedades.count() == 1
    cap.refresh_from_db()
    assert cap.neto_capacidad_ajustada == 504 - 5


@pytest.mark.django_db
def test_eliminar_novedad_recalcula(client, escenario, usuario):
    _, param, cap = escenario
    param.novedades_abiertas = True
    param.save()
    n = Novedad.objects.create(capacidad_sala=cap, citas_afectadas=5, signo="DESCONTAR")
    orm.recalcular(cap)
    client.force_login(usuario)

    client.post(f"/novedades/{n.id}/eliminar/")

    cap.refresh_from_db()
    assert cap.novedades.count() == 0
    assert cap.neto_capacidad_ajustada == 504


@pytest.mark.django_db
def test_editar_novedad_mes_abierto_recalcula(client, escenario, usuario):
    _, param, cap = escenario
    param.novedades_abiertas = True
    param.save()
    n = Novedad.objects.create(capacidad_sala=cap, citas_afectadas=5, signo="DESCONTAR")
    orm.recalcular(cap)
    client.force_login(usuario)

    r = client.get(f"/novedades/{n.id}/editar/")
    assert r.status_code == 200
    assert "Guardar" in r.content.decode()

    r = client.post(
        f"/novedades/{n.id}/editar/",
        {"tipo": "PERMISO", "signo": "DESCONTAR", "citas_afectadas": 9},
    )
    assert r.status_code == 200
    n.refresh_from_db()
    cap.refresh_from_db()
    assert n.citas_afectadas == 9
    assert n.tipo == "PERMISO"
    assert cap.neto_capacidad_ajustada == 504 - 9


@pytest.mark.django_db
def test_editar_novedad_mes_cerrado_no_guarda(client, escenario, usuario):
    _, param, cap = escenario  # novedades_abiertas=False por defecto
    n = Novedad.objects.create(capacidad_sala=cap, citas_afectadas=5, signo="DESCONTAR")
    orm.recalcular(cap)
    client.force_login(usuario)

    r = client.post(
        f"/novedades/{n.id}/editar/",
        {"tipo": "PERMISO", "signo": "DESCONTAR", "citas_afectadas": 9},
    )
    assert r.status_code == 200
    assert "no está habilitado" in r.content.decode()
    n.refresh_from_db()
    assert n.citas_afectadas == 5


@pytest.mark.django_db
def test_cancelar_edicion_novedad(client, escenario, usuario):
    _, param, cap = escenario
    param.novedades_abiertas = True
    param.save()
    n = Novedad.objects.create(capacidad_sala=cap, citas_afectadas=5, signo="DESCONTAR")
    client.force_login(usuario)

    r = client.get(f"/novedades/{n.id}/fila/")
    assert r.status_code == 200
    assert "Editar" in r.content.decode()


@pytest.mark.django_db
def test_toggle_solo_staff(client, escenario, usuario, staff):
    _, param, _ = escenario

    client.force_login(usuario)
    client.post("/novedades/habilitar/", {"parametro": param.id})
    param.refresh_from_db()
    assert param.novedades_abiertas is False  # el no-staff no puede

    client.force_login(staff)
    client.post("/novedades/habilitar/", {"parametro": param.id})
    param.refresh_from_db()
    assert param.novedades_abiertas is True  # el admin sí


@pytest.mark.django_db
def test_novedad_invalida_no_se_guarda(client, escenario, usuario):
    _, param, cap = escenario
    param.novedades_abiertas = True
    param.save()
    client.force_login(usuario)

    r = client.post(
        f"/novedades/agregar/{cap.id}/",
        {"tipo": "INCAPACIDAD", "signo": "DESCONTAR", "citas_afectadas": 0},
    )

    assert r.status_code == 200
    assert cap.novedades.count() == 0
    assert "No se pudo registrar" in r.content.decode()
