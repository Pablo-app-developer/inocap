from django.urls import path

from . import views

app_name = "atenciones"

urlpatterns = [
    path("dinero/", views.dinero, name="dinero"),
    path("resumen-anual/", views.resumen_anual, name="resumen_anual"),
    path("facturacion-presupuesto/", views.facturacion_presupuesto, name="facturacion_presupuesto"),
]
