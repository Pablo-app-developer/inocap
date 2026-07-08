"""
Modelos de capacidad instalada por mes.

Jerarquía:
    ParametroMensual (unidad + año + mes)
        └── CapacidadSala (una fila por sala/mes)   <- corazón del cálculo
                ├── Novedad          (descuentos/sumas de citas)
                ├── TerminoAdicional (para método PERSONALIZADO, ej. Cardiopulmonar)
                └── PatronDiaSemana  (para método POR_DIA_SEMANA, sedes municipales)
    ResumenMensual (indicador de cumplimiento por unidad/mes)

Todos los valores calculados (citas_dia, citas_mes, neto...) se derivan por el
servicio `apps.capacidad.services.calculo` y se persisten como snapshot; nunca
se escriben a mano.
"""

from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import Sala, UnidadNegocio

MESES = [
    (1, "Enero"), (2, "Febrero"), (3, "Marzo"), (4, "Abril"),
    (5, "Mayo"), (6, "Junio"), (7, "Julio"), (8, "Agosto"),
    (9, "Septiembre"), (10, "Octubre"), (11, "Noviembre"), (12, "Diciembre"),
]


class ModoCalculo(models.TextChoices):
    """Cómo se cuentan los días del mes.

    CALENDARIO   -> cuenta días L–V y sábados reales del mes descontando festivos.
    EXCEL_LEGACY -> usa los parámetros fijos (#díasLaV, #sábados/sem, #semanas/mes)
                    tal como el Excel original. Sirve para validar paridad.
    """

    CALENDARIO = "CALENDARIO", "Calendario real (descuenta festivos)"
    EXCEL_LEGACY = "EXCEL_LEGACY", "Parámetros fijos (fidelidad Excel)"


class ParametroMensual(models.Model):
    """Parámetros generales de una unidad de negocio para un mes concreto."""

    unidad_negocio = models.ForeignKey(
        UnidadNegocio, on_delete=models.CASCADE, related_name="parametros"
    )
    anio = models.PositiveIntegerField()
    mes = models.PositiveSmallIntegerField(choices=MESES)

    modo = models.CharField(
        max_length=15, choices=ModoCalculo.choices, default=ModoCalculo.CALENDARIO
    )

    # Parámetros usados en modo EXCEL_LEGACY (y como multiplicador de términos
    # semanales en modo CALENDARIO).
    dias_lav = models.PositiveSmallIntegerField("# Días Lunes a Viernes", default=5)
    sabados_semana = models.PositiveSmallIntegerField("# Sábados por semana", default=1)
    semanas_mes = models.PositiveSmallIntegerField("# Semanas del mes", default=4)

    minutos_hora = models.PositiveSmallIntegerField("Minutos por hora", default=60)
    tiempo_por_cita_min = models.DecimalField(
        "Tiempo por cita (min)", max_digits=6, decimal_places=2, default=30
    )

    novedades_abiertas = models.BooleanField(
        "Ingreso de novedades habilitado", default=False,
        help_text="Si está activo, los usuarios pueden registrar novedades de "
                  "este mes en el módulo de novedades.",
    )

    class Meta:
        verbose_name = "Parámetro mensual"
        verbose_name_plural = "Parámetros mensuales"
        ordering = ["-anio", "mes", "unidad_negocio"]
        constraints = [
            models.UniqueConstraint(
                fields=["unidad_negocio", "anio", "mes"],
                name="uniq_parametro_unidad_anio_mes",
            )
        ]

    def __str__(self) -> str:
        return f"{self.unidad_negocio} {self.get_mes_display()} {self.anio}"


class CapacidadSala(models.Model):
    """Fila de capacidad de una sala en un mes. Núcleo del cálculo."""

    sala = models.ForeignKey(Sala, on_delete=models.CASCADE, related_name="capacidades")
    parametro = models.ForeignKey(
        ParametroMensual, on_delete=models.CASCADE, related_name="capacidades"
    )

    # --- Entradas (editables por el usuario) ---
    # Método POR_HORAS / PERSONALIZADO:
    horas_dia_lav = models.DecimalField(
        "Horas/día L–V", max_digits=6, decimal_places=2, default=0
    )
    horas_dia_sabado = models.DecimalField(
        "Horas/día sábados", max_digits=6, decimal_places=2, default=0
    )
    tiempo_estandar_horas = models.DecimalField(
        "Tiempo estándar (horas)", max_digits=6, decimal_places=3, default=0,
        validators=[MinValueValidator(0.001)],
    )
    ajuste_sobreatencion = models.IntegerField(
        "Ajuste por sobreatenciones", default=0,
        help_text="Citas adicionales por sobreatención (columna I del Excel).",
    )

    # Overrides estructurados (método PERSONALIZADO, ej. Cardiopulmonar).
    # Si son NULL se usan los del ParametroMensual.
    override_dias_lav = models.PositiveSmallIntegerField(null=True, blank=True)
    override_sabados = models.PositiveSmallIntegerField(null=True, blank=True)

    # Método POR_DIA_SEMANA: citas por cada día de la semana. En modo calendario,
    # cada día se multiplica por sus ocurrencias reales en el mes (sin festivos).
    citas_lun = models.PositiveIntegerField("Citas lunes", default=0)
    citas_mar = models.PositiveIntegerField("Citas martes", default=0)
    citas_mie = models.PositiveIntegerField("Citas miércoles", default=0)
    citas_jue = models.PositiveIntegerField("Citas jueves", default=0)
    citas_vie = models.PositiveIntegerField("Citas viernes", default=0)
    citas_sab = models.PositiveIntegerField("Citas sábado", default=0)
    citas_dom = models.PositiveIntegerField("Citas domingo", default=0)
    sabados_alternos = models.BooleanField(
        "Sábado de por medio", default=False,
        help_text="Atiende un sábado sí y uno no (quincenal): cuenta la mitad "
                  "de los sábados del mes, redondeando hacia abajo.",
    )

    observaciones = models.TextField(blank=True)
    horario_laboral = models.TextField(blank=True)

    # --- Salidas (snapshot calculado, no editar a mano) ---
    citas_dia_lav = models.IntegerField(default=0, editable=False)
    citas_dia_sabado = models.IntegerField(default=0, editable=False)
    citas_mes = models.IntegerField(default=0, editable=False)
    citas_mes_total = models.IntegerField(default=0, editable=False)
    neto_capacidad_ajustada = models.IntegerField(default=0, editable=False)

    class Meta:
        verbose_name = "Capacidad de sala (mes)"
        verbose_name_plural = "Capacidades de sala (mes)"
        ordering = ["parametro", "sala"]
        constraints = [
            models.UniqueConstraint(
                fields=["sala", "parametro"], name="uniq_capacidad_sala_parametro"
            )
        ]

    def __str__(self) -> str:
        return f"{self.sala} — {self.parametro}"

    @property
    def citas_por_dia_semana(self) -> tuple:
        """Citas por día (0=lunes … 6=domingo)."""
        return (
            self.citas_lun, self.citas_mar, self.citas_mie, self.citas_jue,
            self.citas_vie, self.citas_sab, self.citas_dom,
        )

    @property
    def citas_semana(self) -> int:
        """Total de citas por semana (suma de todos los días)."""
        return sum(self.citas_por_dia_semana)

    @property
    def total_descontar(self) -> int:
        return sum(n.citas_afectadas for n in self.novedades.all() if n.signo == "DESCONTAR")

    @property
    def total_sumar(self) -> int:
        return sum(n.citas_afectadas for n in self.novedades.all() if n.signo == "SUMAR")


class Signo(models.TextChoices):
    DESCONTAR = "DESCONTAR", "Descontar (−)"
    SUMAR = "SUMAR", "Sumar (+)"


class TipoNovedad(models.TextChoices):
    INCAPACIDAD = "INCAPACIDAD", "Incapacidad"
    PERMISO = "PERMISO", "Permiso"
    PERMISO_VOTACION = "PERMISO_VOTACION", "Permiso por votación"
    VACACIONES = "VACACIONES", "Vacaciones"
    CURSO = "CURSO", "Capacitación aprobada por gerencia"
    REUNION = "REUNION", "Reunión autorizada por gerencia"
    MANTENIMIENTO = "MANTENIMIENTO", "Mantenimiento autorizado"
    FESTIVO = "FESTIVO", "Festivo"
    TEST_EJERCICIO = "TEST_EJERCICIO", "Test de ejercicio"
    CIERRE_SALA = "CIERRE_SALA", "Cierre de sala"
    SESION_EDUCATIVA = "SESION_EDUCATIVA", "Sesión educativa"
    APOYO_SERVICIO = "APOYO_SERVICIO", "Apoyo a otro servicio"
    OTRO = "OTRO", "Otro"


class Novedad(models.Model):
    """Descuento o suma de citas sobre una capacidad de sala.

    La suma de novedades DESCONTAR equivale a la columna 'NOVEDADES A DESCONTAR'
    del Excel (que se ingresaba como '=2+72'); cada sumando es una Novedad.
    """

    capacidad_sala = models.ForeignKey(
        CapacidadSala, on_delete=models.CASCADE, related_name="novedades"
    )
    tipo = models.CharField(max_length=20, choices=TipoNovedad.choices, default=TipoNovedad.OTRO)
    signo = models.CharField(max_length=10, choices=Signo.choices, default=Signo.DESCONTAR)
    citas_afectadas = models.PositiveIntegerField(default=0)
    descripcion = models.CharField(max_length=255, blank=True)
    fecha = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "Novedad"
        verbose_name_plural = "Novedades"
        ordering = ["capacidad_sala", "fecha"]

    def __str__(self) -> str:
        return f"{self.get_signo_display()} {self.citas_afectadas} — {self.get_tipo_display()}"


class Periodicidad(models.TextChoices):
    SEMANAL = "SEMANAL", "Semanal"
    MENSUAL = "MENSUAL", "Mensual"


class TerminoAdicional(models.Model):
    """Término extra en el cálculo de citas mes (método PERSONALIZADO).

    Ejemplo Cardiopulmonar:  ((F×3) + 15×2 + 18) × 4
    -> override_dias_lav=3, override_sabados=0, y dos términos SEMANAL de 30 y 18.
    """

    capacidad_sala = models.ForeignKey(
        CapacidadSala, on_delete=models.CASCADE, related_name="terminos"
    )
    descripcion = models.CharField(max_length=255, blank=True)
    citas = models.IntegerField(default=0)
    periodicidad = models.CharField(
        max_length=10, choices=Periodicidad.choices, default=Periodicidad.SEMANAL
    )

    class Meta:
        verbose_name = "Término adicional"
        verbose_name_plural = "Términos adicionales"
        ordering = ["capacidad_sala"]

    def __str__(self) -> str:
        return f"{self.descripcion or 'Término'}: {self.citas} ({self.get_periodicidad_display()})"


class PatronDiaSemana(models.Model):
    """Patrón de citas por día de la semana (método POR_DIA_SEMANA, municipales).

    Ejemplo Barranca: 'LUNES-MIERCOLES-VIERNES', dias=3, citas_por_dia=16.
    En modo CALENDARIO, `dias_semana` (0=lunes..6=domingo, coma-separado) permite
    contar las ocurrencias reales de esos días en el mes; en modo EXCEL_LEGACY se
    usa el conteo fijo `dias`.
    """

    capacidad_sala = models.ForeignKey(
        CapacidadSala, on_delete=models.CASCADE, related_name="patrones"
    )
    descripcion = models.CharField(max_length=120, blank=True)
    dias = models.PositiveSmallIntegerField("# días (conteo fijo)", default=0)
    citas_por_dia = models.PositiveIntegerField(default=0)
    es_sabado = models.BooleanField(
        default=False,
        help_text="Si es sábado, aporta como total mensual (no se multiplica por semanas).",
    )
    dias_semana = models.CharField(
        max_length=20, blank=True,
        help_text="Días de la semana (0=lun..6=dom) separados por coma, para modo calendario.",
    )

    class Meta:
        verbose_name = "Patrón día de la semana"
        verbose_name_plural = "Patrones día de la semana"
        ordering = ["capacidad_sala"]

    def __str__(self) -> str:
        return f"{self.descripcion}: {self.dias}×{self.citas_por_dia}"


class ResumenMensual(models.Model):
    """Indicador de cumplimiento por unidad/mes (hoja RESUMEN)."""

    unidad_negocio = models.ForeignKey(
        UnidadNegocio, on_delete=models.CASCADE, related_name="resumenes"
    )
    anio = models.PositiveIntegerField()
    mes = models.PositiveSmallIntegerField(choices=MESES)

    # Si meta_atenciones es NULL se deriva de la suma de netos de capacidad.
    meta_atenciones = models.IntegerField(null=True, blank=True)
    atenciones_realizadas = models.IntegerField(default=0)

    valor_facturado = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    presupuesto = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    meta_pct = models.DecimalField(max_digits=5, decimal_places=4, default=0.10)

    class Meta:
        verbose_name = "Resumen mensual"
        verbose_name_plural = "Resúmenes mensuales"
        ordering = ["-anio", "mes"]
        constraints = [
            models.UniqueConstraint(
                fields=["unidad_negocio", "anio", "mes"],
                name="uniq_resumen_unidad_anio_mes",
            )
        ]

    def __str__(self) -> str:
        return f"Resumen {self.unidad_negocio} {self.get_mes_display()} {self.anio}"
