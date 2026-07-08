"""
Datos de ejemplo (seed) basados en la hoja ENERO del Excel del Laboratorio Pulmonar.

Carga:
  - Festivos de Colombia del año indicado.
  - Unidad de negocio "Laboratorio Pulmonar".
  - Sedes y salas del Excel (6 salas principales + 3 sedes municipales).
  - Parámetro mensual de ENERO 2026 y una CapacidadSala por sala, con sus
    novedades, términos (Cardiopulmonar) y patrones (municipales).
  - Se recalcula el snapshot y se crea el ResumenMensual de enero.

Se ejecuta en modo EXCEL_LEGACY para reproducir exactamente los números del Excel;
cambia el `modo` del parámetro a CALENDARIO para recalcular por días reales.

Uso:  python manage.py seed_demo [--anio 2026] [--reset]
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.calendario.festivos_co import festivos_colombia
from apps.calendario.models import Festivo
from apps.capacidad.models import (
    CapacidadSala,
    ModoCalculo,
    Novedad,
    ParametroMensual,
    ResumenMensual,
    Signo,
    TerminoAdicional,
)
from apps.capacidad.services import orm
from apps.core.models import MetodoCalculo, Sala, Sede, UnidadNegocio

H = Decimal("10.5")          # horas/día L–V y sábados (salas principales)
TE = Decimal("0.5")          # tiempo estándar (horas)

# Orden fijo de sedes (principales primero por orden, municipales siempre al
# final en la UI vía la sección "municipales" — ver selectors.vista_mensual).
SEDES_ORDEN = {"Cabecera": 0, "Fosunab": 1, "Barranca": 2, "San Gil": 3, "Málaga": 4}

# Salas principales (método POR_HORAS salvo Cardiopulmonar).
# (nombre, sede, novedades_descontar[list], metodo, terminos[list], overrides)
# El orden de esta lista fija Sala.orden, así la UI siempre muestra:
# Cabecera 1, Cabecera 2, Oscilo, Pletismógrafo 1, Pletismografía 2, Cardiopulmonar.
SALAS_PRINCIPALES = [
    ("Cabecera 1", "Cabecera", [2], MetodoCalculo.POR_HORAS, [], {}),
    ("Cabecera 2", "Cabecera", [2, 72], MetodoCalculo.POR_HORAS, [], {}),
    ("Oscilo", "Fosunab", [6], MetodoCalculo.POR_HORAS, [], {}),
    ("Pletismógrafo 1", "Fosunab", [10, 5, 2], MetodoCalculo.POR_HORAS, [], {}),
    ("Pletismografía 2", "Fosunab", [], MetodoCalculo.POR_HORAS, [], {}),
    ("Cardiopulmonar", "Fosunab", [], MetodoCalculo.PERSONALIZADO, [30, 18],
     {"override_dias_lav": 3, "override_sabados": 0}),
]

# Sedes municipales (método POR_DIA_SEMANA), siempre al final de la UI.
# (nombre, sede, novedades, (lun, mar, mié, jue, vie, sáb, dom), sabados_alternos)
# Málaga atiende 7 citas un sábado de por medio (quincenal).
# Orden fijo: Barrancabermeja, San Gil, Málaga.
SALAS_MUNICIPALES = [
    ("Barrancabermeja", "Barranca", [8, 17], (16, 8, 16, 17, 16, 0, 0), False),
    ("San Gil", "San Gil", [2], (17, 16, 17, 16, 17, 0, 0), False),
    ("Málaga", "Málaga", [6, 15], (16, 16, 16, 16, 15, 7, 0), True),
]


class Command(BaseCommand):
    help = "Carga datos de ejemplo del Laboratorio Pulmonar (hoja ENERO)."

    def add_arguments(self, parser):
        parser.add_argument("--anio", type=int, default=2026)
        parser.add_argument("--reset", action="store_true", help="Borra datos previos de la unidad.")
        parser.add_argument(
            "--modo", choices=["calendario", "legacy"], default="calendario",
            help="calendario = días reales del mes (default); legacy = fijos como el Excel.",
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        anio = opts["anio"]
        modo = ModoCalculo.CALENDARIO if opts["modo"] == "calendario" else ModoCalculo.EXCEL_LEGACY

        # --- Festivos ---
        creados = 0
        for fecha, nombre in festivos_colombia(anio):
            _, nuevo = Festivo.objects.get_or_create(fecha=fecha, defaults={"nombre": nombre})
            creados += int(nuevo)
        self.stdout.write(f"Festivos {anio}: {creados} nuevos.")

        # --- Unidad ---
        unidad, _ = UnidadNegocio.objects.get_or_create(
            codigo="lab-pulmonar", defaults={"nombre": "Laboratorio Pulmonar"}
        )
        if opts["reset"]:
            ParametroMensual.objects.filter(unidad_negocio=unidad, anio=anio).delete()
            Sala.objects.filter(unidad_negocio=unidad).delete()

        # --- Sedes ---
        def sede(nombre, municipal=False):
            obj, creado = Sede.objects.get_or_create(
                codigo=nombre.lower().replace(" ", "-"),
                defaults={
                    "nombre": nombre, "es_municipal": municipal,
                    "orden": SEDES_ORDEN.get(nombre, 0),
                },
            )
            if not creado and obj.orden != SEDES_ORDEN.get(nombre, obj.orden):
                obj.orden = SEDES_ORDEN.get(nombre, obj.orden)
                obj.save(update_fields=["orden"])
            return obj

        for n in ("Cabecera", "Fosunab"):
            sede(n)
        for n in ("Barranca", "San Gil", "Málaga"):
            sede(n, municipal=True)

        # --- Parámetro mensual ENERO ---
        param, _ = ParametroMensual.objects.update_or_create(
            unidad_negocio=unidad, anio=anio, mes=1,
            defaults=dict(
                modo=modo, dias_lav=5, sabados_semana=1,
                semanas_mes=4, minutos_hora=60, tiempo_por_cita_min=30,
            ),
        )

        # --- Salas principales ---
        for orden, (nombre, sede_nombre, novs, metodo, terminos, overrides) in enumerate(SALAS_PRINCIPALES):
            sala, _ = Sala.objects.update_or_create(
                unidad_negocio=unidad, sede=sede(sede_nombre), nombre=nombre, especialidad="",
                defaults={"metodo_calculo": metodo, "atiende_sabados": True, "orden": orden},
            )
            cap, _ = CapacidadSala.objects.update_or_create(
                sala=sala, parametro=param,
                defaults=dict(
                    horas_dia_lav=H, horas_dia_sabado=H, tiempo_estandar_horas=TE,
                    override_dias_lav=overrides.get("override_dias_lav"),
                    override_sabados=overrides.get("override_sabados"),
                ),
            )
            cap.novedades.all().delete()
            for citas in novs:
                Novedad.objects.create(
                    capacidad_sala=cap, citas_afectadas=citas, signo=Signo.DESCONTAR
                )
            cap.terminos.all().delete()
            for citas in terminos:
                TerminoAdicional.objects.create(capacidad_sala=cap, citas=citas)
            orm.recalcular(cap)

        # --- Salas municipales (citas por día de la semana) ---
        for orden, (nombre, sede_nombre, novs, dias_citas, sab_alternos) in enumerate(SALAS_MUNICIPALES):
            lun, mar, mie, jue, vie, sab, dom = dias_citas
            sala, _ = Sala.objects.update_or_create(
                unidad_negocio=unidad, sede=sede(sede_nombre, municipal=True),
                nombre=nombre, especialidad="",
                defaults={
                    "metodo_calculo": MetodoCalculo.POR_DIA_SEMANA,
                    "atiende_sabados": sab > 0,
                    "orden": orden,
                },
            )
            cap, _ = CapacidadSala.objects.update_or_create(
                sala=sala, parametro=param,
                defaults=dict(
                    tiempo_estandar_horas=TE,
                    citas_lun=lun, citas_mar=mar, citas_mie=mie, citas_jue=jue,
                    citas_vie=vie, citas_sab=sab, citas_dom=dom,
                    sabados_alternos=sab_alternos,
                ),
            )
            cap.novedades.all().delete()
            for citas in novs:
                Novedad.objects.create(
                    capacidad_sala=cap, citas_afectadas=citas, signo=Signo.DESCONTAR
                )
            orm.recalcular(cap)

        total = orm.total_neto_unidad(unidad, anio, 1)

        # --- Resumen enero ---
        ResumenMensual.objects.update_or_create(
            unidad_negocio=unidad, anio=anio, mes=1,
            defaults=dict(
                atenciones_realizadas=3034,  # RESUMEN!D6
                presupuesto=Decimal("356834659"), meta_pct=Decimal("0.10"),
            ),
        )

        self.stdout.write(self.style.SUCCESS(
            f"Seed OK. Salas: {Sala.objects.filter(unidad_negocio=unidad).count()} | "
            f"Neto total capacidad enero (meta atenciones) = {total}"
        ))
