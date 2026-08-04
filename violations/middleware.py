from django.shortcuts import render, redirect
from django.contrib.auth import logout
from django.urls import reverse

class ViolationBlockMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Skip checking for super admins
            if request.user.is_superuser:
                return self.get_response(request)
            
            profile = getattr(request.user, 'profile', None)
            if profile and profile.is_blocked_by_violations:
                if request.path != reverse('login') and request.path != reverse('logout'):
                    from django.contrib import messages
                    messages.error(request, "Siz qoidabuzarliklar sababli tizimdan vaqtincha bloklangansiz. Iltimos, tushuntirish xati orqali ruxsat oling.")
                    logout(request)
                    return redirect(reverse('login'))
                
        return self.get_response(request)
