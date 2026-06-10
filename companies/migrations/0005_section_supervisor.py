from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def link_existing_section_supervisors(apps, schema_editor):
    Section = apps.get_model('companies', 'Section')
    UserProfile = apps.get_model('accounts', 'UserProfile')
    for section in Section.objects.all():
        admin_profile = (
            UserProfile.objects.filter(
                section_id=section.pk,
                role='section_admin',
            )
            .order_by('id')
            .first()
        )
        if admin_profile:
            section.supervisor_id = admin_profile.user_id
            section.save(update_fields=['supervisor_id'])


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('companies', '0004_department_supervisor'),
        ('accounts', '0006_link_workers_to_organizations'),
    ]

    operations = [
        migrations.AddField(
            model_name='section',
            name='supervisor',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='supervised_sections',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Bo‘lim nazoratchisi',
            ),
        ),
        migrations.RunPython(link_existing_section_supervisors, migrations.RunPython.noop),
    ]
