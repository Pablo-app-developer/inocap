from django.contrib import admin

from .models import Festivo


@admin.register(Festivo)
class FestivoAdmin(admin.ModelAdmin):
    list_display = ("fecha", "nombre", "es_nacional")
    list_filter = ("es_nacional",)
    date_hierarchy = "fecha"
    search_fields = ("nombre",)
