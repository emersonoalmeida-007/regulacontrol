"""Cria os grupos de perfil (RF01): Administrador, Analista e Consulta."""
from django.db import migrations

GRUPOS = ["Administrador", "Analista", "Consulta"]


def criar(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for nome in GRUPOS:
        Group.objects.get_or_create(name=nome)


def remover(apps, schema_editor):
    apps.get_model("auth", "Group").objects.filter(name__in=GRUPOS).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("licencas", "0001_initial"),
    ]

    operations = [migrations.RunPython(criar, remover)]
