import os
import json
import logging
import urllib.request as urlrequest
import urllib.parse as urlparse
from django.conf import settings
from django.urls import reverse

logger = logging.getLogger(__name__)


class OneIDService:
    """
    One ID (id.egov.uz) SSO OAuth2 integratsiya xizmati.
    """

    def __init__(self):
        self.client_id = getattr(settings, 'ONEID_CLIENT_ID', '') or os.getenv('ONEID_CLIENT_ID', '')
        self.client_secret = getattr(settings, 'ONEID_CLIENT_SECRET', '') or os.getenv('ONEID_CLIENT_SECRET', '')
        self.auth_url = getattr(settings, 'ONEID_AUTH_URL', 'https://sso.egov.uz/sso/oauth/Authorization.do')

    def get_redirect_uri(self, request):
        configured_uri = getattr(settings, 'ONEID_REDIRECT_URI', '') or os.getenv('ONEID_REDIRECT_URI', '')
        if configured_uri:
            return configured_uri
        return request.build_absolute_uri(reverse('oneid-callback'))

    def get_authorization_url(self, request, state=''):
        """
        Foydalanuvchini One ID sahifasiga yo'naltirish URL manzili.
        """
        params = {
            'response_type': 'one_code',
            'client_id': self.client_id,
            'redirect_uri': self.get_redirect_uri(request),
            'scope': 'legal',
            'state': state or 'sopline_oneid_auth',
        }
        return f"{self.auth_url}?{urlparse.urlencode(params)}"

    def exchange_code_for_user_info(self, code, request):
        """
        OneID dan kelgan 'code' orqali access_token va foydalanuvchi ma'lumotlarini olish.
        """
        redirect_uri = self.get_redirect_uri(request)
        payload = {
            'grant_type': 'one_authorization_code',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code': code,
            'redirect_uri': redirect_uri,
        }

        data = urlparse.urlencode(payload).encode('utf-8')
        req = urlrequest.Request(
            self.auth_url,
            data=data,
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'User-Agent': 'Sopline-SafeWork-System/1.0',
            },
            method='POST',
        )

        try:
            with urlrequest.urlopen(req, timeout=15) as resp:
                raw_response = resp.read().decode('utf-8')
                result = json.loads(raw_response)
                return self._parse_oneid_user(result)
        except Exception as e:
            logger.exception("One ID token exchange error")
            return {"error": f"One ID bilan bog'lanishda xatolik: {str(e)}"}

    def _parse_oneid_user(self, data):
        """
        One ID serveridan kelgan ma'lumotlarni Sopline formatiga moslash.
        """
        if not data or 'user_id' not in data and 'pin' not in data and 'pinfl' not in data:
            if 'error' in data:
                return {"error": f"One ID xatosi: {data.get('error_description') or data.get('error')}"}
            return {"error": "One ID foydalanuvchi ma'lumotlari topilmadi."}

        # OneID maydonlari: pin (JShShIR), sur_name, first_name, mid_name, mob_phone_no, pport_no, etc.
        pinfl = data.get('pin') or data.get('pinfl') or ''
        first_name = data.get('first_name', '').strip()
        last_name = data.get('sur_name', '').strip()
        middle_name = data.get('mid_name', '').strip()
        full_name = data.get('full_name') or f"{last_name} {first_name} {middle_name}".strip()

        passport = data.get('pport_no', '').strip()
        passport_series = passport[:2] if len(passport) >= 2 and passport[:2].isalpha() else ''
        passport_number = passport[2:] if passport_series else passport

        phone = data.get('mob_phone_no') or data.get('phone') or ''
        birth_date = data.get('birth_date') or None

        return {
            'pinfl': pinfl,
            'passport_series': passport_series,
            'passport_number': passport_number,
            'first_name': first_name,
            'last_name': last_name,
            'middle_name': middle_name,
            'full_name': full_name,
            'phone_number': phone,
            'birth_date': birth_date,
            'one_id_user_id': data.get('user_id', ''),
            'email': data.get('email', ''),
            'raw_data': data,
        }
