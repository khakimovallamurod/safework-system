from django.db import migrations


def create_default_industries(apps, schema_editor):
    Industry = apps.get_model('industries', 'Industry')
    default_names = [
        "Qurilish",
        "Sanoat",
        "Sog'liqni saqlash",
        "Ta'lim",
    ]
    for name in default_names:
        Industry.objects.get_or_create(name=name)


def reverse_default_industries(apps, schema_editor):
    Industry = apps.get_model('industries', 'Industry')
    Industry.objects.filter(name__in=[
        "Qurilish",
        "Sanoat",
        "Sog'liqni saqlash",
        "Ta'lim",
    ]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('industries', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_default_industries, reverse_default_industries),
    ]
