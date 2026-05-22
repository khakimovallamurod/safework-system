from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def link_existing_supervisors(apps, schema_editor):
    Department = apps.get_model('companies', 'Department')
    UserProfile = apps.get_model('accounts', 'UserProfile')
    for department in Department.objects.all():
        admin_profile = (
            UserProfile.objects.filter(
                department_id=department.pk,
                role='department_admin',
            )
            .order_by('id')
            .first()
        )
        if admin_profile:
            department.supervisor_id = admin_profile.user_id
            department.save(update_fields=['supervisor_id'])


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('companies', '0003_department_section'),
        ('accounts', '0005_fix_default_worker_usernames'),
    ]

    operations = [
        migrations.AddField(
            model_name='department',
            name='supervisor',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='supervised_departments',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Boshqarma nazoratchisi',
            ),
        ),
        migrations.RunPython(link_existing_supervisors, migrations.RunPython.noop),
    ]
