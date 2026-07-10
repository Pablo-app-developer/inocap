from django.urls import path

from . import views

app_name = "atenciones"

urlpatterns = [
    path("dinero/", views.dinero, name="dinero"),
]
