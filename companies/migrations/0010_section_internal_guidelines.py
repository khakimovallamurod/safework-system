import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0009_fix_guideline_recipient_worker_kind'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SectionInternalGuideline',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('pdf_file', models.FileField(upload_to='section_internal_guidelines/')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_section_internal_guidelines', to=settings.AUTH_USER_MODEL)),
                ('section', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='internal_guidelines', to='companies.section')),
            ],
            options={
                'verbose_name_plural': 'Section internal guidelines',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='SectionInternalGuidelineDispatch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sent_at', models.DateTimeField(auto_now_add=True)),
                ('guideline', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='dispatches', to='companies.sectioninternalguideline')),
                ('sent_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sent_section_internal_guideline_dispatches', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name_plural': 'Section internal guideline dispatches',
                'ordering': ['-sent_at'],
            },
        ),
        migrations.CreateModel(
            name='SectionInternalGuidelineRecipient',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_acknowledged', models.BooleanField(default=False)),
                ('acknowledged_at', models.DateTimeField(blank=True, null=True)),
                ('dispatch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recipients', to='companies.sectioninternalguidelinedispatch')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='section_internal_guideline_receipts', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name_plural': 'Section internal guideline recipients',
                'ordering': ['user__profile__full_name', 'user__username'],
            },
        ),
        migrations.AddConstraint(
            model_name='sectioninternalguidelinerecipient',
            constraint=models.UniqueConstraint(fields=('dispatch', 'user'), name='unique_section_internal_guideline_recipient_per_dispatch'),
        ),
    ]
