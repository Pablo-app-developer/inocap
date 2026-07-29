import django.db.models.deletion
from django.db import migrations, models

# (codigo, nombre, ayuda, orden) — mismo orden y textos que el TextChoices anterior.
TIPOS = [
    ("INCAPACIDAD", "Incapacidad", "", 0),
    ("PERMISO", "Permiso", "", 1),
    ("PERMISO_VOTACION", "Permiso por votación", "", 2),
    ("VACACIONES", "Vacaciones", "", 3),
    ("DIA_FAMILIA", "Día de la familia", "", 4),
    ("CURSO", "Capacitación aprobada por gerencia", "", 5),
    ("REUNION", "Reunión autorizada por gerencia", "", 6),
    ("REUNION_GENERAL", "Reunión", "", 7),
    ("MANTENIMIENTO", "Mantenimiento autorizado", "", 8),
    ("FESTIVO", "Festivo", "", 9),
    (
        "TEST_EJERCICIO", "Prueba/procedimiento (desplaza consultas)",
        "Ej.: test de ejercicio, toma de electrolitos", 10,
    ),
    ("CIERRE_SALA", "Cierre de sala", "", 11),
    ("SESION_EDUCATIVA", "Sesión educativa", "", 12),
    ("APOYO_SERVICIO", "Apoyo a otro servicio", "", 13),
    ("OTRO", "Otro", "", 14),
]


def poblar_tipos(apps, schema_editor):
    TipoNovedad = apps.get_model("capacidad", "TipoNovedad")
    for codigo, nombre, ayuda, orden in TIPOS:
        TipoNovedad.objects.get_or_create(
            codigo=codigo, defaults={"nombre": nombre, "ayuda": ayuda, "orden": orden},
        )


def migrar_novedades_a_fk(apps, schema_editor):
    Novedad = apps.get_model("capacidad", "Novedad")
    TipoNovedad = apps.get_model("capacidad", "TipoNovedad")
    por_codigo = {t.codigo: t.id for t in TipoNovedad.objects.all()}
    for n in Novedad.objects.all():
        n.tipo_fk_id = por_codigo[n.tipo]
        n.save(update_fields=["tipo_fk"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("capacidad", "0009_alter_novedad_tipo"),
    ]

    operations = [
        migrations.CreateModel(
            name="TipoNovedad",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo", models.SlugField(max_length=30, unique=True)),
                ("nombre", models.CharField(max_length=80)),
                ("ayuda", models.CharField(blank=True, max_length=200)),
                ("activo", models.BooleanField(default=True)),
                ("orden", models.PositiveIntegerField(default=0)),
            ],
            options={
                "verbose_name": "Tipo de novedad",
                "verbose_name_plural": "Tipos de novedad",
                "ordering": ["orden", "nombre"],
            },
        ),
        migrations.RunPython(poblar_tipos, noop),
        migrations.AddField(
            model_name="novedad",
            name="tipo_fk",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="novedades_tmp",
                to="capacidad.tiponovedad",
            ),
        ),
        migrations.RunPython(migrar_novedades_a_fk, noop),
        migrations.RemoveField(model_name="novedad", name="tipo"),
        migrations.RenameField(model_name="novedad", old_name="tipo_fk", new_name="tipo"),
        migrations.AlterField(
            model_name="novedad",
            name="tipo",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="novedades",
                to="capacidad.tiponovedad",
            ),
        ),
    ]
