from django.contrib import admin
from .models import PPEType, PPEIssue

@admin.register(PPEType)
class PPETypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)

@admin.register(PPEIssue)
class PPEIssueAdmin(admin.ModelAdmin):
    list_display = ('employee', 'ppe_type', 'issue_date', 'expiration_date', 'condition', 'status')
    list_filter = ('status', 'condition', 'ppe_type')
    search_fields = ('employee__first_name', 'employee__last_name', 'employee__username')
