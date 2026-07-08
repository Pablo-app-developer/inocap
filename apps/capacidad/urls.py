from django.urls import path

from . import views

app_name = "capacidad"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("mensual/", views.mensual, name="mensual"),
    path("mensual/crear/", views.crear_mes, name="crear_mes"),
    path("capacidad/<int:pk>/editar/", views.editar_capacidad, name="editar_capacidad"),
    path("capacidad/<int:pk>/metodo/", views.cambiar_metodo, name="cambiar_metodo"),
    path("capacidad/<int:pk>/fila/", views.fila_capacidad, name="fila_capacidad"),
    path("novedades/", views.novedades, name="novedades"),
    path("novedades/agregar/<int:cap_id>/", views.agregar_novedad, name="agregar_novedad"),
    path("novedades/<int:pk>/eliminar/", views.eliminar_novedad, name="eliminar_novedad"),
    path("novedades/habilitar/", views.toggle_novedades, name="toggle_novedades"),
]
