from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('accounts', '0010_alter_userprofile_role')]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='inspection_detail_access',
            field=models.BooleanField(default=False, help_text='O‘chiq bo‘lsa inspeksiya faqat umumiy son va foizlarni ko‘radi.', verbose_name='Inspeksiyaga xodimlar tafsilotlarini ko‘rsatish'),
        ),
    ]
