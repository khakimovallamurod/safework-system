import os
from pathlib import Path
import pymysql

pymysql.install_as_MySQLdb()

BASE_DIR = Path(__file__).resolve().parent.parent


def load_simple_env_file(env_path):
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue

        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_simple_env_file(BASE_DIR / '.env')

# SECURITY WARNING: keep the secret key used in production secret.
SECRET_KEY = os.getenv(
    'DJANGO_SECRET_KEY',
    'django-insecure-obdh3*9edyyg1ud&m#h2^5w@a0i!d5+@e@*@l@end&08z_%1s0',
)

# SECURITY WARNING: don't run with debug turned on in production.
DEBUG = os.getenv('DJANGO_DEBUG', 'True').lower() == 'true'

# Production & Local Allowed Hosts
ALLOWED_HOSTS = [
    'sopline.uz',
    '.sopline.uz',
    'www.sopline.uz',
    '127.0.0.1',
    'localhost',
    '0.0.0.0',
]
extra_hosts = os.getenv('DJANGO_ALLOWED_HOSTS', '')
if extra_hosts:
    for h in extra_hosts.split(','):
        h_clean = h.strip().strip('"').strip("'")
        if h_clean and h_clean not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(h_clean)
if '*' in ALLOWED_HOSTS:
    pass

# CSRF Trusted Origins for HTTPS production
CSRF_TRUSTED_ORIGINS = [
    'https://sopline.uz',
    'https://www.sopline.uz',
    'http://sopline.uz',
    'http://www.sopline.uz',
    'http://127.0.0.1:8000',
    'http://localhost:8000',
]
extra_csrf = os.getenv('DJANGO_CSRF_TRUSTED_ORIGINS', '')
if extra_csrf:
    for origin in extra_csrf.split(','):
        o_clean = origin.strip().strip('"').strip("'")
        if o_clean and o_clean not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(o_clean)

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core.apps.CoreConfig',
    'accounts',
    'super_admin',
    'organization_leader',
    'department_admin',
    'section_admin',
    'worker',
    'industries',
    'companies',
    'professions',
    'ppe',
    'violations',
    'inspection',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'violations.middleware.ViolationBlockMiddleware',
    'accounts.middleware.WorkerEntryGuidelineGateMiddleware',
    'inspection.middleware.InspectionReadOnlyMiddleware',
    'accounts.middleware.UserActivityMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'accounts.context_processors.sopline_role_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'safeworkdb',
        'USER': 'root',
        'PASSWORD': '',
        'HOST': '127.0.0.1',
        'PORT': '3306',
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        }
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 6,
        },
    },
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Samarkand'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
MEDIA_URL = '/uploads/'
MEDIA_ROOT = BASE_DIR / 'uploads'
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'

# Basic production hardening (effective when DEBUG=False).
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'SAMEORIGIN'

SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin-allow-popups'

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '').strip()
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-3.6-flash')
TELEGRAM_BOT_TOKEN = os.getenv('TOKEN', os.getenv('TELEGRAM_BOT_TOKEN', '')).strip()

# One ID (id.egov.uz) SSO OAuth2 Configuration
ONEID_CLIENT_ID = os.getenv('ONEID_CLIENT_ID', '').strip()
ONEID_CLIENT_SECRET = os.getenv('ONEID_CLIENT_SECRET', '').strip()
ONEID_AUTH_URL = os.getenv('ONEID_AUTH_URL', 'https://sso.egov.uz/sso/oauth/Authorization.do').strip()
ONEID_REDIRECT_URI = os.getenv('ONEID_REDIRECT_URI', '').strip()
