import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute("ALTER TABLE ichki_nizom_yuborish ADD COLUMN is_active tinyint(1) NOT NULL DEFAULT 1;")
    cursor.execute("ALTER TABLE ichki_nizom_yuborish ADD COLUMN start_time datetime(6) NULL;")
    cursor.execute("ALTER TABLE ichki_nizom_yuborish ADD COLUMN registration_end_time datetime(6) NULL;")
    cursor.execute("ALTER TABLE ichki_nizom_yuborish ADD COLUMN active_until datetime(6) NULL;")
