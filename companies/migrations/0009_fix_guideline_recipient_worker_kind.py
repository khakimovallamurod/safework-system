from django.db import migrations


def reclassify_worker_recipients(apps, schema_editor):
    GuidelineDispatchRecipient = apps.get_model('companies', 'GuidelineDispatchRecipient')
    for receipt in GuidelineDispatchRecipient.objects.filter(recipient_kind='section').select_related('section'):
        section = receipt.section
        if section and section.supervisor_id and receipt.user_id != section.supervisor_id:
            receipt.recipient_kind = 'worker'
            receipt.save(update_fields=['recipient_kind'])


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0008_entry_guidelines'),
    ]

    operations = [
        migrations.RunPython(reclassify_worker_recipients, migrations.RunPython.noop),
    ]
