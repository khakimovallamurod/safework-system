# Sopline System

Sopline System - Django asosida qurilgan multi-role web platforma.
Tizimda `Tashkilot rahbari` va `Ishchi` rollari bo'yicha alohida dashboard, autentifikatsiya va huquqlar boshqaruvi mavjud.

## Asosiy imkoniyatlar

- Landing page:
  - platforma haqida ma'lumot
  - imkoniyatlar
  - navbar va footer
  - bog'lanish va manzil bo'limi
  - sohalarni rasmlar bilan ko'rsatish
- Login/logout va ro'yxatdan o'tish
- Rolga asoslangan kirish (RBAC)
- Tashkilot rahbari uchun:
  - faqat o'z sohasidagi `Kasb turlari`ni ko'rish va boshqarish
- Ishchi uchun:
  - o'z sohasi bo'yicha `Kasb turlari`ni ko'rish
- Kasb turiga PDF nizom yuklash
  - Faqat `.pdf`
  - Maksimal hajm: `1MB`
- Dashboard statistikasi:
  - Tashkilot rahbari: tashkilot nomi, soha nomi, kasb turlari soni
  - Ishchi: tashkilot, soha, jamoa va kasb turlari soni

## Texnologiyalar

- Python 3
- Django
- SQLite3
- Tailwind CSS (CDN)
- Bootstrap Icons
- SweetAlert2

## Loyiha tuzilmasi

- `core/` - global Django sozlamalari (`settings.py`, `urls.py`)
- `accounts/` - login/logout, register, dashboard, user profile va role mixinlar
- `industries/` - sohalar moduli
- `companies/` - kompaniyalar moduli
- `professions/` - kasb turlari va nizom fayllari moduli
- `templates/` - UI shablonlar
- `static/` - frontend helper JS fayllar
- `media/` - yuklangan fayllar (nizom PDF)

## O'rnatish va ishga tushirish

1. Loyihaga kiring:

```bash
cd /home/xakimov-allamurod/Documents/computer-vision/sopline-system
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
venv/bin/python manage.py migrate
```

5. Serverni ishga tushiring:

```bash
venv/bin/python manage.py runserver
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
- Register tanlash: `http://127.0.0.1:8000/register/`
- Dashboard: `http://127.0.0.1:8000/dashboard/`
- Sohalar: `http://127.0.0.1:8000/industries/`
- Kasb turlari: `http://127.0.0.1:8000/professions/`

## Eslatma

- `Tashkilot rahbari` va `Ishchi` o'zlari ro'yxatdan o'tadi.
- Bloklangan foydalanuvchi login vaqtida ogohlantirish oladi va tizimga kira olmaydi.
- `Kasb turlari` uchun fayl validatsiyasi model darajasida ishlaydi (`pdf`, `<=1MB`).
