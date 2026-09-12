import time
from django.core.cache import cache

MAX_ATTEMPTS = 5
LOCKOUT_DURATION = 600  # 10 minutes in seconds


def get_client_ip(request):
    """Foydalanuvchining haqiqiy IP manzilini aniqlash."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
    return ip


def check_login_rate_limit(request, username):
    """
    Parol terish (Brute-force) hujumlariga qarshi tekshiruv.
    Agar 5 ta muvaffaqiyatsiz urinish qayd etilgan bo'lsa, kirish 10 daqiqaga bloklanadi.
    Returns: (is_allowed: bool, wait_seconds: int)
    """
    ip = get_client_ip(request)
    ip_key = f"rl_login_ip_{ip}"
    user_key = f"rl_login_user_{username.lower().strip()}"

    ip_data = cache.get(ip_key) or {'count': 0, 'locked_until': 0}
    user_data = cache.get(user_key) or {'count': 0, 'locked_until': 0}

    now = int(time.time())

    # IP bloklanganmi?
    if ip_data.get('locked_until', 0) > now:
        return False, ip_data['locked_until'] - now

    # Username bloklanganmi?
    if user_data.get('locked_until', 0) > now:
        return False, user_data['locked_until'] - now

    return True, 0


def record_failed_login(request, username):
    """Noto'g'ri kirish urinishini qayd etish."""
    ip = get_client_ip(request)
    ip_key = f"rl_login_ip_{ip}"
    user_key = f"rl_login_user_{username.lower().strip()}"

    now = int(time.time())

    for key in (ip_key, user_key):
        data = cache.get(key) or {'count': 0, 'locked_until': 0}
        data['count'] += 1

        if data['count'] >= MAX_ATTEMPTS:
            data['locked_until'] = now + LOCKOUT_DURATION
            cache.set(key, data, LOCKOUT_DURATION)
        else:
            cache.set(key, data, 300)  # 5 daqiqa saqlash


def reset_login_rate_limit(request, username):
    """Muvaffaqiyatli kirishdan so'ng hisoblagichlarni tozalash."""
    ip = get_client_ip(request)
    cache.delete(f"rl_login_ip_{ip}")
    cache.delete(f"rl_login_user_{username.lower().strip()}")
