"""
Pruebas de los importadores (convenios, mapeo de unidades y atenciones)
con archivos xlsx sintéticos pequeños.
"""

import datetime

import openpyxl
import pytest
from django.core.management import call_command

from apps.atenciones.models import (
    Atencion,
    Entidad,
    MapeoEspecialidad,
    TarifaConvenio,
    normalizar,
)
from apps.core.models import UnidadNegocio


def _xlsx(ruta, hoja, filas):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = hoja
    for fila in filas:
        ws.append(fila)
    wb.save(ruta)
    return str(ruta)


def test_normalizar():
    assert normalizar("  Clínica de Alergías ") == "CLINICA DE ALERGIAS"
    assert normalizar("SANITAS  EPS   SA") == "SANITAS EPS SA"
    assert normalizar(None) == ""


@pytest.mark.django_db
def test_importar_convenios_upsert(tmp_path):
    ruta = _xlsx(tmp_path / "conv.xlsx", "contratacion", [
        ["Id", "Nit", "Entidad", "ServicioId", "CodigoServicio", "Servicio",
         "TipoContratacion", "Porcentaje", "ValorContratado", "Observacion"],
        ["1", "900", "SANITAS EPS SA", "5", "891704", "POLISOMNOGRAFIA", "ValorAbierto", "0", "470000", ""],
        ["2", "900", "SANITAS EPS SA", "6", "893801", "ESPIROMETRIA", "ValorAbierto", "0", "49537", ""],
        ["3", "800", "ECOPETROL S.A.", "5", "891704", "POLISOMNOGRAFIA", "ValorAbierto", "0", "500000", ""],
    ])
    call_command("importar_convenios", ruta)

    assert Entidad.objects.count() == 2
    assert TarifaConvenio.objects.count() == 3
    t = TarifaConvenio.objects.get(entidad__nombre="SANITAS EPS SA", codigo_servicio="891704")
    assert t.valor == 470000

    # Re-importar con valor cambiado actualiza (upsert), no duplica.
    ruta2 = _xlsx(tmp_path / "conv2.xlsx", "contratacion", [
        ["Id", "Nit", "Entidad", "ServicioId", "CodigoServicio", "Servicio",
         "TipoContratacion", "Porcentaje", "ValorContratado", "Observacion"],
        ["1", "900", "SANITAS EPS SA", "5", "891704", "POLISOMNOGRAFIA", "ValorAbierto", "0", "999999", ""],
    ])
    call_command("importar_convenios", ruta2)
    t.refresh_from_db()
    assert t.valor == 999999
    assert TarifaConvenio.objects.count() == 3


@pytest.mark.django_db
def test_importar_mapeo_unidades_match_tolerante(tmp_path):
    # Ya existe la unidad SIN tilde; el Excel viene CON tilde → no debe duplicar.
    UnidadNegocio.objects.create(nombre="Clínica de Alergias", codigo="clinica-alergias")
    ruta = _xlsx(tmp_path / "map.xlsx", "Unidades", [
        ["Especialidad", "UNIDAD DE NEGOCIO"],
        ["Alergología", "Clínica de Alergías"],
        ["Laboratorio Pulmonar", "Laboratorio Pulmonar"],
    ])
    call_command("importar_mapeo_unidades", ruta)

    assert MapeoEspecialidad.objects.count() == 2
    assert UnidadNegocio.objects.filter(nombre__icontains="alerg").count() == 1  # sin duplicar
    m = MapeoEspecialidad.objects.get(especialidad="Alergología")
    assert m.unidad_negocio.nombre == "Clínica de Alergias"


@pytest.mark.django_db
def test_importar_atenciones(tmp_path):
    lab = UnidadNegocio.objects.create(nombre="Laboratorio Pulmonar", codigo="lab-pulmonar")
    MapeoEspecialidad.objects.create(especialidad="Laboratorio Pulmonar", unidad_negocio=lab)

    encabezado = ["AG D", "TC Codi", "TC Nomb", "AG Asistenc", "EN Codi", "EN Nomb",
                  "Valor Servicio", "Sede", "Sala", "Especialidad", "Unidad de Negocio"]
    ruta = _xlsx(tmp_path / "aten.xlsx", "BASE", [
        encabezado,
        [datetime.datetime(2026, 1, 5), "893801", "ESPIROMETRIA PRE Y POST", "Salida",
         "EPS005", "SANITAS EPS SA", "49537", "Sede Cabecera", "LAB1",
         "Laboratorio Pulmonar", "Laboratorio Pulmonar"],
        # con fecha en texto y SIN columna unidad (usa mapeo por especialidad)
        ["06/01/2026", "893801", "ESPIROMETRIA PRE Y POST", "Cancelada",
         "EPS005", "SANITAS EPS SA", "49537", "Sede Cabecera", "LAB1",
         "Laboratorio Pulmonar", None],
        # sin fecha → omitida
        [None, "893801", "X", "Salida", "", "OTRA EPS", "0", "", "", "", None],
    ])
    call_command("importar_atenciones", ruta, "--hoja", "BASE")

    assert Atencion.objects.count() == 2
    a = Atencion.objects.get(estado="Salida")
    assert (a.anio, a.mes) == (2026, 1)
    assert a.unidad_negocio == lab
    assert a.entidad.nombre == "SANITAS EPS SA"
    assert a.entidad.creada_automaticamente is True

    b = Atencion.objects.get(estado="Cancelada")
    assert b.fecha == datetime.date(2026, 1, 6)
    assert b.unidad_negocio == lab  # derivada del mapeo de especialidad

    # Reemplazar el año: no duplica.
    call_command("importar_atenciones", ruta, "--hoja", "BASE", "--reemplazar-anio", "2026")
    assert Atencion.objects.count() == 2
