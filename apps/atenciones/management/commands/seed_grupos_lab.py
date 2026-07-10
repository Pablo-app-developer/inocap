"""
Siembra los grupos de servicio del Laboratorio Pulmonar (tabla validada con el
usuario a partir de los 31 códigos reales de 2026).

Reglas confirmadas:
  - Las variantes con sufijo '/ PROGRAMAS' (CPI_*) e '/ INVESTIGACIÓN' (CSI_*)
    son el mismo servicio que su base CUPS.
  - La resistencia SIMPLE (893809) NO es la pre y post → va en 'Otras pruebas'.
  - Los volúmenes basales (CLB_01) van en 'Otras pruebas' (reasignable en admin).

Re-ejecutable (update_or_create). Uso:
    python manage.py seed_grupos_lab
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.atenciones.models import CodigoServicioGrupo, GrupoServicio
from apps.core.models import UnidadNegocio

GRUPOS = [
    # (nombre, códigos, es_otras)
    ("Espirometría pre y post", ["893805", "CPI_15", "CSI_11"], False),
    ("Capacidad de difusión", ["893806", "CPI_26", "CSI_12"], False),
    ("Volúmenes pre y post", ["893701", "CPI_22"], False),
    ("FeNO", ["893819", "CPI_21", "CSI_13"], False),
    ("Oscilometría", ["893825", "CPI_24"], False),
    ("Resistencias pre y post", ["893813"], False),
    ("Prueba de ejercicio cardiopulmonar", ["894101", "CPI_27"], False),
    ("Espirometría simple", ["893808"], False),
    ("Broncoprovocación con metacolina", ["893815"], False),
    ("Broncomotricidad con ejercicio", ["893820", "CPI_25"], False),
    ("Electrolitos en sudor", ["903612", "903613", "903607"], False),
    ("Otras pruebas", ["893810", "893811", "893812", "893809", "CLB_01", "CLB_02"], True),
]


class Command(BaseCommand):
    help = "Siembra los grupos de servicio del Laboratorio Pulmonar."

    @transaction.atomic
    def handle(self, *args, **opts):
        try:
            lab = UnidadNegocio.objects.get(codigo="lab-pulmonar")
        except UnidadNegocio.DoesNotExist:
            raise CommandError("No existe la unidad 'lab-pulmonar'. Corre seed_demo primero.")

        grupos = codigos = 0
        for orden, (nombre, lista, es_otras) in enumerate(GRUPOS):
            grupo, _ = GrupoServicio.objects.update_or_create(
                unidad_negocio=lab, nombre=nombre,
                defaults={"orden": orden, "es_otras": es_otras},
            )
            grupos += 1
            for codigo in lista:
                CodigoServicioGrupo.objects.update_or_create(grupo=grupo, codigo=codigo)
                codigos += 1

        self.stdout.write(self.style.SUCCESS(
            f"Grupos Lab Pulmonar: {grupos} grupos, {codigos} códigos asignados."
        ))
