"""
Modelos núcleo: Unidad de Negocio, Sede y Sala.

La estructura refleja el archivo "TABLAS PARA CREAR PLATAFORMA WEB":
- Las SEDES son un catálogo global (FOSUNAB, CABECERA, BARRANCA, ...).
- Las UNIDADES DE NEGOCIO también (LABORATORIO PULMONAR, CLINICA DE SUEÑO, ...).
- Una SALA/consultorio/ítem pertenece a una (Sede, Unidad) y define CÓMO se
  calcula su capacidad (método de cálculo).
"""

from django.db import models


class MetodoCalculo(models.TextChoices):
    """Cómo se calcula la capacidad de una sala.

    POR_HORAS      -> citas/día = ROUND(horas_día / tiempo_estándar). (Salas Cabecera/Fosunab)
    POR_DIA_SEMANA -> citas/día se definen por patrón de días de la semana. (Sedes municipales)
    PERSONALIZADO  -> POR_HORAS con overrides estructurados y términos adicionales. (Cardiopulmonar)
    """

    POR_HORAS = "POR_HORAS", "Por horas ÷ tiempo estándar"
    POR_DIA_SEMANA = "POR_DIA_SEMANA", "Por patrón de días de la semana"
    PERSONALIZADO = "PERSONALIZADO", "Personalizado (overrides estructurados)"


class UnidadNegocio(models.Model):
    nombre = models.CharField(max_length=120, unique=True)
    codigo = models.SlugField(max_length=40, unique=True)
    activo = models.BooleanField(default=True)
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Unidad de negocio"
        verbose_name_plural = "Unidades de negocio"
        ordering = ["orden", "nombre"]

    def __str__(self) -> str:
        return self.nombre


class Sede(models.Model):
    nombre = models.CharField(max_length=120, unique=True)
    codigo = models.SlugField(max_length=40, unique=True)
    es_municipal = models.BooleanField(
        default=False,
        help_text="Sedes municipales (Barranca, San Gil, Málaga) usan parametrización propia.",
    )
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Sede"
        verbose_name_plural = "Sedes"
        ordering = ["nombre"]

    def __str__(self) -> str:
        return self.nombre


class Sala(models.Model):
    """Sala / consultorio / ítem con capacidad calculable."""

    unidad_negocio = models.ForeignKey(
        UnidadNegocio, on_delete=models.PROTECT, related_name="salas"
    )
    sede = models.ForeignKey(Sede, on_delete=models.PROTECT, related_name="salas")
    nombre = models.CharField(max_length=150)
    especialidad = models.CharField(max_length=80, blank=True)

    metodo_calculo = models.CharField(
        max_length=20,
        choices=MetodoCalculo.choices,
        default=MetodoCalculo.POR_HORAS,
    )
    atiende_sabados = models.BooleanField(default=True)

    activo = models.BooleanField(default=True)
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Sala / ítem"
        verbose_name_plural = "Salas / ítems"
        ordering = ["unidad_negocio", "orden", "nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["unidad_negocio", "sede", "nombre", "especialidad"],
                name="uniq_sala_por_unidad_sede_nombre",
            )
        ]

    def __str__(self) -> str:
        base = f"{self.nombre} ({self.sede})"
        return f"{base} — {self.especialidad}" if self.especialidad else base

    # Explicación corta de cada método, reutilizada en tooltips de la UI.
    METODO_AYUDA = {
        MetodoCalculo.POR_HORAS: (
            "Por horas ÷ tiempo estándar. Citas/día = redondear(horas ÷ tiempo). "
            "Cuenta los días L–V y sábados reales del mes (descuenta festivos)."
        ),
        MetodoCalculo.POR_DIA_SEMANA: (
            "Por patrón de días de la semana. Las citas/día se definen por día "
            "(ej. Lun-Mié-Vie: 16). Cuenta las ocurrencias reales en el mes."
        ),
        MetodoCalculo.PERSONALIZADO: (
            "Personalizado (receta semanal × semanas) con overrides y términos. "
            "No lo afectan los días ni festivos del mes; siempre es semanal."
        ),
    }

    @property
    def metodo_ayuda(self) -> str:
        return self.METODO_AYUDA.get(self.metodo_calculo, "")
