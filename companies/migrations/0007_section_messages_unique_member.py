from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('companies', '0006_sectionmembership'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='sectionmembership',
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name='sectionmembership',
            constraint=models.UniqueConstraint(fields=('user',), name='unique_section_member_per_user'),
        ),
        migrations.CreateModel(
            name='SectionMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('body', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('section', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='companies.section')),
                ('sender', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sent_section_messages', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name_plural': 'Section messages',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='SectionMessageReceipt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_read', models.BooleanField(default=False)),
                ('read_at', models.DateTimeField(blank=True, null=True)),
                ('message', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='receipts', to='companies.sectionmessage')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='section_message_receipts', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name_plural': 'Section message receipts',
                'unique_together': {('message', 'user')},
            },
        ),
    ]
