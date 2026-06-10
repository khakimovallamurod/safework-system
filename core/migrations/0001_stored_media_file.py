from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='StoredMediaFile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('path', models.CharField(db_index=True, max_length=255, unique=True)),
                ('data', models.BinaryField()),
                ('content_type', models.CharField(default='application/octet-stream', max_length=128)),
                ('size', models.PositiveIntegerField(default=0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Saqlangan fayl',
                'verbose_name_plural': 'Saqlangan fayllar',
            },
        ),
    ]
