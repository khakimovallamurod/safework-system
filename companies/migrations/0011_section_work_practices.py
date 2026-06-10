import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0010_section_internal_guidelines'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SectionWorkPractice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('start_time', models.DateTimeField()),
                ('end_time', models.DateTimeField()),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_work_practices', to=settings.AUTH_USER_MODEL)),
                ('section', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='work_practices', to='companies.section')),
            ],
            options={
                'verbose_name_plural': 'Section work practices',
                'ordering': ['-start_time', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='SectionWorkPracticeAssignee',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assignees', to='companies.sectionworkpractice')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='work_practice_assignments', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name_plural': 'Section work practice assignees',
            },
        ),
        migrations.AddConstraint(
            model_name='sectionworkpracticeassignee',
            constraint=models.UniqueConstraint(fields=('practice', 'user'), name='unique_work_practice_assignee'),
        ),
    ]
