from django.contrib import admin

from accounts.models import UserActivitySummary, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'role', 'organization_name', 'industry', 'is_new_registration', 'created_at')
    list_filter = ('role', 'is_new_registration', 'industry')
    search_fields = ('full_name', 'organization_name', 'user__username')


@admin.register(UserActivitySummary)
class UserActivitySummaryAdmin(admin.ModelAdmin):
    list_display = ('user', 'last_seen_at', 'total_active_seconds', 'requests_count', 'last_path')
    search_fields = ('user__username', 'user__profile__full_name', 'last_path')
    readonly_fields = ('first_seen_at', 'last_seen_at', 'last_path', 'total_active_seconds', 'requests_count')
