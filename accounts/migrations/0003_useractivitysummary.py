from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UserActivitySummary',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('first_seen_at', models.DateTimeField(blank=True, null=True)),
                ('last_seen_at', models.DateTimeField(blank=True, null=True)),
                ('last_path', models.CharField(blank=True, max_length=255)),
                ('total_active_seconds', models.PositiveIntegerField(default=0)),
                ('requests_count', models.PositiveIntegerField(default=0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='activity_summary', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name_plural': 'User activity summaries',
                'db_table': 'foydalanuvchi_faollik',
                'ordering': ['-last_seen_at'],
            },
        ),
    ]
