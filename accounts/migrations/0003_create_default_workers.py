from django.contrib.auth.hashers import make_password
from django.db import migrations


def create_default_workers(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    UserProfile = apps.get_model('accounts', 'UserProfile')

    default_workers = [
        {'username': f'worker{i}', 'full_name': f'Xodim {i}', 'phone_number': f'+99890123{40 + i:02d}'}
        for i in range(1, 11)
    ]

    for worker_data in default_workers:
        username = worker_data['username']
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'password': make_password('worker123'),
                'is_active': True,
            },
        )
        if created:
            UserProfile.objects.create(
                user=user,
                role='worker',
                full_name=worker_data['full_name'],
                phone_number=worker_data['phone_number'],
            )


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_alter_userprofile_phone_number'),
    ]

    operations = [
        migrations.RunPython(create_default_workers),
    ]
