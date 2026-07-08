"""
Pruebas de control de acceso por unidad en las vistas (evitar IDOR): un usuario
sin acceso a una unidad no debe poder ver ni operar sus datos, aunque adivine
el id en la URL o en el formulario. El sidebar solo debe listar sus unidades.
"""

from decimal import Decimal

import pytest
from django.contrib.auth.models import User

from apps.capacidad.models import CapacidadSala, ModoCalculo, ParametroMensual
from apps.core.models import MetodoCalculo, PerfilUsuario, Sala, Sede, UnidadNegocio


@pytest.fixture
def escenario(db):
    """Dos unidades de negocio independientes, cada una con su sala/capacidad."""
    sede = Sede.objects.create(nombre="Cabecera", codigo="cabecera")

    unidad_a = UnidadNegocio.objects.create(nombre="Laboratorio Pulmonar", codigo="lab-pulmonar")
    param_a = ParametroMensual.objects.create(
        unidad_negocio=unidad_a, anio=2026, mes=1, modo=ModoCalculo.EXCEL_LEGACY,
    )
    sala_a = Sala.objects.create(
        unidad_negocio=unidad_a, sede=sede, nombre="Sala A", metodo_calculo=MetodoCalculo.POR_HORAS,
    )
    cap_a = CapacidadSala.objects.create(
        sala=sala_a, parametro=param_a, tiempo_estandar_horas=Decimal("0.5"),
    )

    unidad_b = UnidadNegocio.objects.create(nombre="Clínica de Sueño", codigo="clinica-sueno")
    param_b = ParametroMensual.objects.create(
        unidad_negocio=unidad_b, anio=2026, mes=1, modo=ModoCalculo.EXCEL_LEGACY,
        novedades_abiertas=True,
    )
    sala_b = Sala.objects.create(
        unidad_negocio=unidad_b, sede=sede, nombre="Sala B", metodo_calculo=MetodoCalculo.POR_HORAS,
    )
    cap_b = CapacidadSala.objects.create(
        sala=sala_b, parametro=param_b, tiempo_estandar_horas=Decimal("0.5"),
    )

    return unidad_a, unidad_b, cap_a, cap_b, param_a, param_b


@pytest.fixture
def operador(db, escenario):
    """Usuario staff (para poder togglear novedades) con acceso SOLO a la unidad A."""
    unidad_a = escenario[0]
    user = User.objects.create_user("operador", password="x", is_staff=True)
    perfil = PerfilUsuario.objects.create(usuario=user)
    perfil.unidades_negocio.add(unidad_a)
    return user


@pytest.mark.django_db
def test_mensual_con_unidad_ajena_cae_a_la_propia(client, escenario, operador):
    unidad_a, unidad_b, *_ = escenario
    client.force_login(operador)

    r = client.get(f"/mensual/?unidad={unidad_b.id}")

    assert r.status_code == 200
    html = r.content.decode()
    assert "Sala A" in html
    assert "Sala B" not in html


@pytest.mark.django_db
def test_sidebar_solo_lista_unidades_accesibles(client, escenario, operador):
    unidad_a, unidad_b, *_ = escenario
    client.force_login(operador)

    html = client.get("/mensual/").content.decode()

    assert unidad_a.nombre in html
    assert unidad_b.nombre not in html


@pytest.mark.django_db
def test_crear_mes_en_unidad_ajena_es_403(client, escenario, operador):
    unidad_a, unidad_b, *_ = escenario
    client.force_login(operador)

    r = client.post("/mensual/crear/", {"unidad": unidad_b.id, "anio": 2026, "mes": 2})

    assert r.status_code == 403
    assert not ParametroMensual.objects.filter(unidad_negocio=unidad_b, anio=2026, mes=2).exists()


@pytest.mark.django_db
def test_agregar_novedad_en_unidad_ajena_es_403(client, escenario, operador):
    _, _, _, cap_b, _, _ = escenario
    client.force_login(operador)

    r = client.post(
        f"/novedades/agregar/{cap_b.id}/",
        {"tipo": "INCAPACIDAD", "signo": "DESCONTAR", "citas_afectadas": 3},
    )

    assert r.status_code == 403
    assert cap_b.novedades.count() == 0


@pytest.mark.django_db
def test_editar_capacidad_en_unidad_ajena_es_403(client, escenario, operador):
    _, _, _, cap_b, _, _ = escenario
    client.force_login(operador)

    r = client.get(f"/capacidad/{cap_b.id}/editar/")

    assert r.status_code == 403


@pytest.mark.django_db
def test_toggle_novedades_en_unidad_ajena_es_403(client, escenario, operador):
    _, _, _, _, _, param_b = escenario
    client.force_login(operador)

    r = client.post("/novedades/habilitar/", {"parametro": param_b.id})

    assert r.status_code == 403
    param_b.refresh_from_db()
    assert param_b.novedades_abiertas is True  # sin cambios


@pytest.mark.django_db
def test_superusuario_ve_ambas_unidades_en_sidebar(client, escenario, django_user_model):
    unidad_a, unidad_b, *_ = escenario
    admin = django_user_model.objects.create_superuser("jefe2", password="x")
    client.force_login(admin)

    html = client.get("/mensual/").content.decode()

    assert unidad_a.nombre in html
    assert unidad_b.nombre in html
