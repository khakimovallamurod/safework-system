import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0007_section_messages_unique_member'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='EntryGuideline',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('pdf_file', models.FileField(upload_to='entry_guidelines/')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_entry_guidelines', to=settings.AUTH_USER_MODEL)),
                ('department', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='entry_guidelines', to='companies.department')),
            ],
            options={
                'verbose_name_plural': 'Entry guidelines',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='GuidelineDispatch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sent_at', models.DateTimeField(auto_now_add=True)),
                ('guideline', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='dispatches', to='companies.entryguideline')),
                ('sent_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sent_guideline_dispatches', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name_plural': 'Guideline dispatches',
                'ordering': ['-sent_at'],
            },
        ),
        migrations.CreateModel(
            name='GuidelineDispatchRecipient',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('recipient_kind', models.CharField(choices=[('section', 'Bo‘lim'), ('worker', 'Xodim')], max_length=16)),
                ('is_acknowledged', models.BooleanField(default=False)),
                ('acknowledged_at', models.DateTimeField(blank=True, null=True)),
                ('dispatch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recipients', to='companies.guidelinedispatch')),
                ('section', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='guideline_recipients', to='companies.section')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='guideline_dispatch_receipts', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name_plural': 'Guideline dispatch recipients',
                'ordering': ['section__name', 'user__profile__full_name'],
            },
        ),
        migrations.AddConstraint(
            model_name='guidelinedispatchrecipient',
            constraint=models.UniqueConstraint(fields=('dispatch', 'user'), name='unique_guideline_recipient_per_dispatch'),
        ),
    ]
