from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0002_repair_internal_guideline_schedule_columns'),
    ]

    operations = [
        migrations.AddField(
            model_name='sectionworkpracticeassignee',
            name='accepted_by_responsible',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='sectionworkpracticeassignee',
            name='accepted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
