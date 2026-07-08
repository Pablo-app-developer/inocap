"""
Pruebas del control de acceso por unidad de negocio (apps.core.accesos).
"""

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied

from apps.core import accesos
from apps.core.models import PerfilUsuario, UnidadNegocio


@pytest.fixture
def unidad_a(db):
    return UnidadNegocio.objects.create(nombre="Laboratorio Pulmonar", codigo="lab-pulmonar")


@pytest.fixture
def unidad_b(db):
    return UnidadNegocio.objects.create(nombre="Clínica de Sueño", codigo="clinica-sueno")


@pytest.fixture
def superusuario(db):
    return User.objects.create_superuser("jefe", password="x")


@pytest.fixture
def operador(db, unidad_a):
    user = User.objects.create_user("operador", password="x")
    perfil = PerfilUsuario.objects.create(usuario=user)
    perfil.unidades_negocio.add(unidad_a)
    return user


@pytest.mark.django_db
def test_superusuario_ve_todas_las_unidades(superusuario, unidad_a, unidad_b):
    vistas = set(accesos.unidades_accesibles(superusuario))
    assert vistas == {unidad_a, unidad_b}


@pytest.mark.django_db
def test_usuario_sin_perfil_no_ve_ninguna(unidad_a, unidad_b):
    user = User.objects.create_user("sin_perfil", password="x")
    assert list(accesos.unidades_accesibles(user)) == []


@pytest.mark.django_db
def test_usuario_ve_solo_sus_unidades_asignadas(operador, unidad_a, unidad_b):
    vistas = set(accesos.unidades_accesibles(operador))
    assert vistas == {unidad_a}


@pytest.mark.django_db
def test_tiene_acceso(operador, unidad_a, unidad_b):
    assert accesos.tiene_acceso(operador, unidad_a) is True
    assert accesos.tiene_acceso(operador, unidad_b) is False


@pytest.mark.django_db
def test_verificar_acceso_lanza_permission_denied(operador, unidad_b):
    with pytest.raises(PermissionDenied):
        accesos.verificar_acceso(operador, unidad_b)


@pytest.mark.django_db
def test_verificar_acceso_no_lanza_si_tiene_permiso(operador, unidad_a):
    accesos.verificar_acceso(operador, unidad_a)  # no debe lanzar
