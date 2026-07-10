"""
Atenciones reales (Medicloud) y tarifas de convenios.

Estos datos alimentan la fase "capacidad en $":
  mezcla de servicios y de entidades (por unidad de negocio + mes, solo
  atenciones con estado 'Salida') × tarifas de convenios (cruce por
  entidad + código CUPS) × capacidad ajustada de la app.

Cruces:
  Atencion.entidad        ← EN Nomb normalizado (Entidad.nombre_normalizado)
  Atencion.unidad_negocio ← columna 'Unidad de Negocio' del Excel o, en su
                            defecto, MapeoEspecialidad (réplica de la hoja
                            'Unidades': Especialidad → Unidad de negocio)
  TarifaConvenio          ← (entidad, codigo_servicio CUPS)

IMPORTANTE privacidad: NO se importan datos personales de pacientes
(nombres, documentos, teléfonos, diagnósticos, antecedentes). Solo las
columnas operativas necesarias para las mezclas y tarifas.
"""

from __future__ import annotations

import unicodedata

from django.db import models

from apps.core.models import UnidadNegocio

# Estado de asistencia que cuenta como atención realizada (decisión de negocio:
# solo "Salida"; Cancelada / No Atención / Asignada / Recepción / Atención no).
ESTADO_REALIZADA = "Salida"


def normalizar(texto) -> str:
    """Normaliza nombres para cruces tolerantes: sin tildes, mayúsculas,
    espacios colapsados. Ej. 'Clínica de Alergías ' -> 'CLINICA DE ALERGIAS'."""
    s = unicodedata.normalize("NFKD", str(texto or "").strip())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.upper().split())


class Entidad(models.Model):
    """EPS / pagador. Se crea desde convenios (con NIT) o automáticamente al
    importar atenciones cuyo EN Nomb no exista aún (sin NIT)."""

    nombre = models.CharField(max_length=180)
    nombre_normalizado = models.CharField(max_length=180, unique=True, editable=False)
    nit = models.CharField(max_length=30, blank=True)
    creada_automaticamente = models.BooleanField(
        default=False,
        help_text="Creada al importar atenciones (no venía en convenios).",
    )

    class Meta:
        verbose_name = "Entidad"
        verbose_name_plural = "Entidades"
        ordering = ["nombre"]

    def save(self, *args, **kwargs):
        self.nombre_normalizado = normalizar(self.nombre)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.nombre


class TarifaConvenio(models.Model):
    """Valor contratado de un servicio (código CUPS) con una entidad.
    Fuente: archivo VALORES CONTRATACION (hoja 'contratacion')."""

    entidad = models.ForeignKey(Entidad, on_delete=models.CASCADE, related_name="tarifas")
    codigo_servicio = models.CharField("Código servicio (CUPS)", max_length=30, db_index=True)
    nombre_servicio = models.CharField(max_length=200, blank=True)
    tipo_contratacion = models.CharField(max_length=60, blank=True)
    porcentaje = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    valor = models.DecimalField("Valor contratado", max_digits=14, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Tarifa de convenio"
        verbose_name_plural = "Tarifas de convenios"
        ordering = ["entidad", "codigo_servicio"]
        constraints = [
            models.UniqueConstraint(
                fields=["entidad", "codigo_servicio"], name="uniq_tarifa_entidad_codigo"
            )
        ]

    def __str__(self) -> str:
        return f"{self.entidad} · {self.codigo_servicio}: {self.valor}"


class MapeoEspecialidad(models.Model):
    """Especialidad (Medicloud) → Unidad de negocio.

    Réplica administrable de la hoja 'Unidades' del Excel (el VLOOKUP que
    agregaba la columna 'Unidad de Negocio'). Necesario porque la API de
    Medicloud NO trae esa columna."""

    especialidad = models.CharField(max_length=120)
    especialidad_normalizada = models.CharField(max_length=120, unique=True, editable=False)
    unidad_negocio = models.ForeignKey(
        UnidadNegocio, on_delete=models.CASCADE, related_name="especialidades_mapeadas"
    )

    class Meta:
        verbose_name = "Mapeo especialidad → unidad"
        verbose_name_plural = "Mapeos especialidad → unidad"
        ordering = ["especialidad"]

    def save(self, *args, **kwargs):
        self.especialidad_normalizada = normalizar(self.especialidad)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.especialidad} → {self.unidad_negocio}"


class GrupoServicio(models.Model):
    """Grupo de servicios para reportes/mezclas (ej. 'Espirometría pre y post'
    agrupa el CUPS 893805 y sus variantes /PROGRAMAS e /INVESTIGACIÓN).

    Regla confirmada con el usuario: las variantes con sufijo son el mismo
    servicio que su base; la resistencia SIMPLE no es la misma pre y post."""

    unidad_negocio = models.ForeignKey(
        UnidadNegocio, on_delete=models.CASCADE, related_name="grupos_servicio"
    )
    nombre = models.CharField(max_length=120)
    orden = models.PositiveIntegerField(default=0)
    es_otras = models.BooleanField(
        "Grupo residual ('Otras pruebas')", default=False,
        help_text="Recoge además cualquier código sin asignar de la unidad.",
    )

    class Meta:
        verbose_name = "Grupo de servicio"
        verbose_name_plural = "Grupos de servicio"
        ordering = ["unidad_negocio", "orden", "nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["unidad_negocio", "nombre"], name="uniq_grupo_unidad_nombre"
            )
        ]

    def __str__(self) -> str:
        return f"{self.nombre} ({self.unidad_negocio})"


class CodigoServicioGrupo(models.Model):
    """Asignación de un código de servicio (TC Codi) a un grupo."""

    grupo = models.ForeignKey(GrupoServicio, on_delete=models.CASCADE, related_name="codigos")
    codigo = models.CharField(max_length=30, db_index=True)

    class Meta:
        verbose_name = "Código de servicio del grupo"
        verbose_name_plural = "Códigos de servicio del grupo"
        constraints = [
            models.UniqueConstraint(fields=["grupo", "codigo"], name="uniq_codigo_por_grupo")
        ]

    def __str__(self) -> str:
        return f"{self.codigo} → {self.grupo.nombre}"


class Atencion(models.Model):
    """Una atención (cita) de Medicloud. Sin datos personales del paciente."""

    fecha = models.DateField(db_index=True)
    anio = models.PositiveSmallIntegerField(db_index=True, editable=False)
    mes = models.PositiveSmallIntegerField(db_index=True, editable=False)

    codigo_servicio = models.CharField(max_length=30, db_index=True)   # TC Codi
    nombre_servicio = models.CharField(max_length=200, blank=True)     # TC Nomb
    estado = models.CharField(max_length=30, db_index=True)            # AG Asistenc

    entidad = models.ForeignKey(
        Entidad, on_delete=models.PROTECT, null=True, blank=True, related_name="atenciones"
    )
    entidad_codigo = models.CharField(max_length=30, blank=True)       # EN Codi

    unidad_negocio = models.ForeignKey(
        UnidadNegocio, on_delete=models.PROTECT, null=True, blank=True, related_name="atenciones"
    )
    especialidad = models.CharField(max_length=120, blank=True)
    sede_nombre = models.CharField(max_length=120, blank=True)         # Sede (texto crudo)
    sala_nombre = models.CharField(max_length=120, blank=True)         # Sala (texto crudo)
    valor_servicio = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Atención"
        verbose_name_plural = "Atenciones"
        indexes = [
            models.Index(fields=["unidad_negocio", "anio", "mes", "estado"]),
        ]

    def save(self, *args, **kwargs):
        self.anio = self.fecha.year
        self.mes = self.fecha.month
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.fecha} {self.codigo_servicio} ({self.estado})"
