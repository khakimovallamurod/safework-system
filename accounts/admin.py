from django.contrib import admin

from accounts.models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'role', 'organization_name', 'industry', 'is_new_registration', 'created_at')
    list_filter = ('role', 'is_new_registration', 'industry')
    search_fields = ('full_name', 'organization_name', 'user__username')
