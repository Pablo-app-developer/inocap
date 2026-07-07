from django.urls import path

from . import views

app_name = "capacidad"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("mensual/", views.mensual, name="mensual"),
    path("capacidad/<int:pk>/editar/", views.editar_capacidad, name="editar_capacidad"),
    path("capacidad/<int:pk>/fila/", views.fila_capacidad, name="fila_capacidad"),
]
