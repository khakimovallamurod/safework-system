from django.db import migrations


def fix_default_worker_usernames(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    UserProfile = apps.get_model('accounts', 'UserProfile')

    for i in range(1, 11):
        phone = f'+99890123{40 + i:02d}'
        old_username = f'worker{i}'
        try:
            user = User.objects.get(username=old_username)
        except User.DoesNotExist:
            continue

        profile = UserProfile.objects.filter(user=user).first()
        if not profile or profile.phone_number != phone:
            continue

        if User.objects.filter(username=phone).exists():
            continue

        user.username = phone
        user.save(update_fields=['username'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_userprofile_department_userprofile_section_and_more'),
    ]

    operations = [
        migrations.RunPython(fix_default_worker_usernames),
    ]
