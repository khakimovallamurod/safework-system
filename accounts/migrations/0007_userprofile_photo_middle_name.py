from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_link_workers_to_organizations'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='middle_name',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='profile_photo',
            field=models.ImageField(blank=True, null=True, upload_to='profile_photos/'),
        ),
    ]
