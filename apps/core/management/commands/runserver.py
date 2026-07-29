from django.contrib.staticfiles.management.commands.runserver import (
    Command as StaticfilesRunserverCommand,
)


class Command(StaticfilesRunserverCommand):
    """El puerto 8000 suele estar ocupado en este equipo; 8001 es el default."""

    default_port = "8001"
