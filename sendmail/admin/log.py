from django.contrib import admin

from sendmail.admin.admin_utils import get_message_preview
from sendmail.models.log import Log


class LogInline(admin.TabularInline):
    model = Log
    readonly_fields = fields = ['date', 'status', 'exception_type', 'message']
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Log)
class LogAdmin(admin.ModelAdmin):
    list_display = ('date', 'email', 'status', get_message_preview)
