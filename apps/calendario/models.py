"""
Calendario: festivos que reducen los días hábiles del mes.

El motor de cálculo en modo CALENDARIO cuenta los días L–V y sábados reales de
cada mes y descuenta los festivos que caen en esos días. Así la capacidad varía
según el calendario del mes/año (requisito explícito del proyecto).
"""

from django.db import models


class Festivo(models.Model):
    fecha = models.DateField(unique=True)
    nombre = models.CharField(max_length=120)
    es_nacional = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Festivo"
        verbose_name_plural = "Festivos"
        ordering = ["fecha"]

    def __str__(self) -> str:
        return f"{self.fecha:%Y-%m-%d} — {self.nombre}"
