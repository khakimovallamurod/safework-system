from accounts.mixins import RoleContextMixin
from accounts.notifications import get_unread_notifications_count


def safework_role_context(request):
    if not request.user.is_authenticated:
        return {}
    mixin = RoleContextMixin()
    mixin.request = request
    context = mixin.get_role_context()
    if context.get('is_section_admin') or context.get('is_section_member'):
        context['unread_notifications_count'] = get_unread_notifications_count(request.user)
    else:
        context['unread_notifications_count'] = 0
    return context
