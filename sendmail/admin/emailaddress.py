from django.contrib import admin

from sendmail.models.emailaddress import Recipient
from sendmail.models.recipients_list import RecipientsList
from sendmail.settings import get_email_address_model


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



def merge_recipients_lists(modeladmin, request, queryset):
    all_recipients = set()
    for recipients_list in queryset:
        all_recipients.update(recipients_list.recipients.all())

    merged_name = '+'.join(recipients_list.name for recipients_list in queryset)

    new_list = modeladmin.model.objects.create(name=merged_name)
    new_list.recipients.set(all_recipients)
    new_list.save()

    modeladmin.message_user(
        request,
        f'Recipients list "{merged_name}" created successfully.'
    )

merge_recipients_lists.short_description = 'Create a new merged list from selected'


@admin.register(RecipientsList)
class RecipientsAdmin(admin.ModelAdmin):
    filter_horizontal = ['recipients']
    actions = [merge_recipients_lists]
