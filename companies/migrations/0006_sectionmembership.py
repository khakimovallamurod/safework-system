from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def backfill_section_memberships(apps, schema_editor):
    UserProfile = apps.get_model('accounts', 'UserProfile')
    SectionMembership = apps.get_model('companies', 'SectionMembership')
    for profile in UserProfile.objects.filter(role='worker', section_id__isnull=False):
        SectionMembership.objects.get_or_create(
            section_id=profile.section_id,
            user_id=profile.user_id,
        )


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('companies', '0005_section_supervisor'),
    ]

    operations = [
        migrations.CreateModel(
            name='SectionMembership',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('assigned_at', models.DateTimeField(auto_now_add=True)),
                ('section', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='memberships', to='companies.section')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='section_memberships', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name_plural': 'Section memberships',
                'ordering': ['-assigned_at'],
                'unique_together': {('section', 'user')},
            },
        ),
        migrations.RunPython(backfill_section_memberships, migrations.RunPython.noop),
    ]
