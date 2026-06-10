from django.contrib.auth.hashers import make_password
from django.db import migrations


def seed_workers(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    UserProfile = apps.get_model('accounts', 'UserProfile')

    for i in range(20):
        phone = f'+9989012345{i:02d}'
        full_name = f'Ishchi {i + 1}'

        user, created = User.objects.get_or_create(
            username=phone,
            defaults={
                'first_name': 'Ishchi',
                'last_name': str(i + 1),
                'password': make_password('123456'),
                'is_active': True,
            },
        )
        if not created:
            user.password = make_password('123456')
            user.is_active = True
            user.save(update_fields=['password', 'is_active'])

        UserProfile.objects.update_or_create(
            user=user,
            defaults={
                'role': 'worker',
                'full_name': full_name,
                'phone_number': phone,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0008_alter_userprofile_role_alter_userprofile_table'),
    ]

    operations = [
        migrations.RunPython(seed_workers, migrations.RunPython.noop),
    ]

