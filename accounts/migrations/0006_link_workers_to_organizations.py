from django.db import migrations
from django.db.models import Q


def link_orphan_workers_to_leaders(apps, schema_editor):
    UserProfile = apps.get_model('accounts', 'UserProfile')

    for leader in UserProfile.objects.filter(role='organization_leader'):
        org_name = (leader.organization_name or '').strip()
        if not org_name and not leader.industry_id:
            continue

        orphans = UserProfile.objects.filter(role='worker', organization_name='')
        if leader.industry_id:
            orphans = orphans.filter(Q(industry_id=leader.industry_id) | Q(industry__isnull=True))

        update_fields = {}
        if org_name:
            update_fields['organization_name'] = org_name
        if leader.industry_id:
            update_fields['industry_id'] = leader.industry_id
        if update_fields:
            orphans.update(**update_fields)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_fix_default_worker_usernames'),
    ]

    operations = [
        migrations.RunPython(link_orphan_workers_to_leaders, migrations.RunPython.noop),
    ]
