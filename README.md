# SafeWork System

SafeWork System - Django asosida qurilgan ichki boshqaruv tizimi.
Tizimda super admin va kompaniya egasi rollari bo'yicha soha, kompaniya va kasb turlari boshqariladi.

## Asosiy imkoniyatlar

- Login/logout orqali autentifikatsiya
- Rolga asoslangan kirish (RBAC)
- Super admin uchun:
  - `Sohalar` CRUD (qo'shish, tahrirlash, o'chirish, qidirish, saralash)
  - `Kompaniyalar` CRUD (login/parol auto generatsiya bilan)
  - `Kasb turlari` CRUD va kompaniya bo'yicha filter
- Kompaniya egasi uchun:
  - Faqat o'z sohasidagi `Kasb turlari`ni ko'rish va boshqarish
- Kasb turiga PDF nizom yuklash
  - Faqat `.pdf`
  - Maksimal hajm: `1MB`
- Dashboard statistikasi:
  - Super admin: jami sohalar va kompaniyalar soni
  - Kompaniya egasi: kompaniya nomi, soha nomi, kasb turlari soni

## Texnologiyalar

- Python 3
- Django
- SQLite3
- Tailwind CSS (CDN)
- Bootstrap Icons
- SweetAlert2

## Loyiha tuzilmasi

- `core/` - global Django sozlamalari (`settings.py`, `urls.py`)
- `accounts/` - login/logout, dashboard, role mixinlar
- `industries/` - sohalar moduli
- `companies/` - kompaniyalar moduli
- `professions/` - kasb turlari va nizom fayllari moduli
- `templates/` - UI shablonlar
- `static/` - frontend helper JS fayllar
- `media/` - yuklangan fayllar (nizom PDF)

## O'rnatish va ishga tushirish

1. Loyihaga kiring:

```bash
cd /home/xakimov-allamurod/Documents/computer-vision/safework-system
```

2. Virtual muhitni yoqing (agar kerak bo'lsa):

```bash
source venv/bin/activate
```

3. Kutubxonalarni o'rnating:

```bash
pip install -r requerments.txt
```

4. Migratsiyalarni qo'llang:

```bash
python manage.py migrate
```

5. Super admin yarating:

```bash
python manage.py createsuperuser
```

6. Serverni ishga tushiring:

```bash
python manage.py runserver
```

## Muhit o'zgaruvchilari (ixtiyoriy)

`core/settings.py` quyidagilarni qo'llab-quvvatlaydi:

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG` (`True` yoki `False`)
- `DJANGO_ALLOWED_HOSTS` (vergul bilan ajratilgan)

Agar berilmasa, default qiymatlar ishlatiladi.

## URL manzillar

- Home: `http://127.0.0.1:8000/`
- Login: `http://127.0.0.1:8000/login/`
- Dashboard: `http://127.0.0.1:8000/dashboard/`
- Sohalar: `http://127.0.0.1:8000/industries/`
- Kompaniyalar: `http://127.0.0.1:8000/companies/`
- Kasb turlari: `http://127.0.0.1:8000/professions/`

## Eslatma

- Yangi kompaniya yaratilganda `username` va `password` avtomatik generatsiya qilinadi.
- Kompaniya o'chirilsa, unga bog'langan Django user ham o'chiriladi.
- `Kasb turlari` uchun fayl validatsiyasi model darajasida ishlaydi (`pdf`, `<=1MB`).
