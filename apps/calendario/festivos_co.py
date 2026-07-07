"""
Generación de festivos de Colombia para cualquier año.

Reglas:
- Fijos: 1-ene, 1-may, 20-jul, 7-ago, 8-dic, 25-dic.
- Ley Emiliani (se trasladan al lunes siguiente si no caen en lunes):
  Reyes (6-ene), San José (19-mar), San Pedro y San Pablo (29-jun),
  N. S. del Rosario de Chiquinquirá (9-jul, Ley 2578 de 2026, rige Ley 51/1983),
  Asunción (15-ago), Día de la Raza (12-oct), Todos los Santos (1-nov),
  Independencia de Cartagena (11-nov).
- Basados en Pascua (Domingo de Resurrección, cómputo occidental):
  Jueves Santo (Pascua−3) y Viernes Santo (Pascua−2): NO se trasladan.
  Ascensión (Pascua+39), Corpus Christi (Pascua+60) y Sagrado Corazón (Pascua+68):
  se trasladan al lunes siguiente.
"""

from __future__ import annotations

from datetime import date, timedelta

# Festivos adicionales no cubiertos por las reglas generales (conmemoraciones
# puntuales de un solo año). Editables aquí o directamente en la BD.
FESTIVOS_EXTRA: dict[int, list[tuple[date, str]]] = {}

# Año a partir del cual rige la Ley 2578 de 2026 (N. S. del Rosario de Chiquinquirá).
ANIO_LEY_CHIQUINQUIRA = 2026


def domingo_de_pascua(anio: int) -> date:
    """Algoritmo de Butcher (Pascua occidental / gregoriana)."""
    a = anio % 19
    b = anio // 100
    c = anio % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = ((h + l - 7 * m + 114) % 31) + 1
    return date(anio, mes, dia)


def _siguiente_lunes(d: date) -> date:
    """Traslada al lunes siguiente si no es lunes (regla Emiliani)."""
    if d.weekday() == 0:  # ya es lunes
        return d
    return d + timedelta(days=(7 - d.weekday()))


def festivos_colombia(anio: int) -> list[tuple[date, str]]:
    """Devuelve [(fecha, nombre), ...] ordenado por fecha."""
    pascua = domingo_de_pascua(anio)
    festivos: list[tuple[date, str]] = []

    # Fijos
    festivos += [
        (date(anio, 1, 1), "Año Nuevo"),
        (date(anio, 5, 1), "Día del Trabajo"),
        (date(anio, 7, 20), "Día de la Independencia"),
        (date(anio, 8, 7), "Batalla de Boyacá"),
        (date(anio, 12, 8), "Inmaculada Concepción"),
        (date(anio, 12, 25), "Navidad"),
    ]

    # Emiliani (traslado a lunes)
    festivos += [
        (_siguiente_lunes(date(anio, 1, 6)), "Reyes Magos"),
        (_siguiente_lunes(date(anio, 3, 19)), "San José"),
        (_siguiente_lunes(date(anio, 6, 29)), "San Pedro y San Pablo"),
        (_siguiente_lunes(date(anio, 8, 15)), "Asunción de la Virgen"),
        (_siguiente_lunes(date(anio, 10, 12)), "Día de la Raza"),
        (_siguiente_lunes(date(anio, 11, 1)), "Todos los Santos"),
        (_siguiente_lunes(date(anio, 11, 11)), "Independencia de Cartagena"),
    ]

    # Basados en Pascua — sin traslado
    festivos += [
        (pascua - timedelta(days=3), "Jueves Santo"),
        (pascua - timedelta(days=2), "Viernes Santo"),
    ]
    # Basados en Pascua — con traslado a lunes
    festivos += [
        (_siguiente_lunes(pascua + timedelta(days=39)), "Ascensión del Señor"),
        (_siguiente_lunes(pascua + timedelta(days=60)), "Corpus Christi"),
        (_siguiente_lunes(pascua + timedelta(days=68)), "Sagrado Corazón"),
    ]

    # Ley 2578 de 2026: Día Nacional de N. S. del Rosario de Chiquinquirá (9-jul),
    # sujeto a Ley Emiliani (traslado a lunes). En 2026, 9-jul (jueves) -> 13-jul.
    if anio >= ANIO_LEY_CHIQUINQUIRA:
        festivos.append(
            (_siguiente_lunes(date(anio, 7, 9)), "Nuestra Señora del Rosario de Chiquinquirá")
        )

    # Festivos adicionales por año (conmemoraciones puntuales), evitando duplicar fechas.
    fechas_existentes = {f for f, _ in festivos}
    for fecha, nombre in FESTIVOS_EXTRA.get(anio, []):
        if fecha not in fechas_existentes:
            festivos.append((fecha, nombre))

    return sorted(festivos, key=lambda x: x[0])
