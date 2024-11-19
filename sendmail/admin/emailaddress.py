from django.contrib import admin

from sendmail.models.emailaddress import Recipient
from sendmail.settings import get_email_address_model
from sendmail.models.recipients_list import RecipientsList
from sendmail import mail


class RecipientInline(admin.TabularInline):
    model = Recipient
    extra = 0

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(get_email_address_model())
class EmailAddressAdmin(admin.ModelAdmin):
    search_fields = ('email', 'first_name', 'last_name')
    list_display = ('email', 'first_name', 'last_name', 'gender', 'is_blocked')

# def send_many_action(modeladmin, request, queryset):
#     letter = queryset.first()
#     mail.send_many(
#         recipients=letter.
#     )



@admin.register(RecipientsList)
class RecipientsAdmin(admin.ModelAdmin):
    pass
