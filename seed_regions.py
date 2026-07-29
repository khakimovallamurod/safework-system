import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from accounts.models import Region

regions = [
    'Andijon viloyati', 'Buxoro viloyati', 'Farg\'ona viloyati',
    'Jizzax viloyati', 'Xorazm viloyati', 'Namangan viloyati',
    'Navoiy viloyati', 'Qashqadaryo viloyati', 'Qoraqalpog\'iston Respublikasi',
    'Samarqand viloyati', 'Sirdaryo viloyati', 'Surxondaryo viloyati',
    'Toshkent viloyati', 'Toshkent shahri'
]

for region_name in regions:
    Region.objects.get_or_create(name=region_name)

print("Viloyatlar bazaga qo'shildi.")
