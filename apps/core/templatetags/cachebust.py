"""Evita que el navegador siga usando una versión vieja de un estático
(app.css, chart.min.js, ...) cacheada de una visita anterior: cada archivo se
sirve con `?v=<fecha de modificación>`, así que un cambio en el archivo
cambia la URL y el navegador lo vuelve a descargar sin que haya que pedirle
al usuario un hard refresh."""

import os

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static

register = template.Library()


@register.simple_tag
def static_v(path):
    url = static(path)
    ruta_absoluta = finders.find(path)
    if ruta_absoluta:
        try:
            return f"{url}?v={int(os.path.getmtime(ruta_absoluta))}"
        except OSError:
            pass
    return url
