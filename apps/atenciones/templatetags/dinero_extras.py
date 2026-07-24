from django import template

register = template.Library()


@register.filter
def porcentaje(fraccion):
    """Convierte una fracción (0.44) al valor de porcentaje (44) para mostrar."""
    if fraccion is None:
        return None
    return fraccion * 100
