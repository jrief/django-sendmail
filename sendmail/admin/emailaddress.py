from django.contrib import admin

from sendmail.models.emailaddress import EmailAddress, Recipient


class RecipientInline(admin.TabularInline):
    model = Recipient
    extra = 0

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(EmailAddress)
class EmailAddressAdmin(admin.ModelAdmin):
    search_fields = ('email', 'first_name', 'last_name')
    list_display = ('email', 'first_name', 'last_name', 'gender', 'is_blocked')
