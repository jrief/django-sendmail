from django.contrib import admin
from django.utils.html import format_html
from sendmail.models.emailmodel import STATUS, EmailModel
from sendmail.models.newsletter import Newsletter, STATUS as NewsletterStatus

from jsoneditor.forms import JSONEditor
from django.db.models.fields.json import JSONField


from django import forms
from django.utils.safestring import mark_safe
import json


class JSONTableWidget(forms.Widget):
    template_name = 'widgets/json_table.html'

    def render(self, name, value, attrs=None, renderer=None):
        # Parse the JSON value or set it to an empty dictionary
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                value = {}

        # Build table rows for existing data
        rows = ""
        if value is None:
            value = {}
        for key, val in value.items():
            rows += f"""
            <tr>
                <td><input type="text" name="{name}_key[]" value="{key}" class="form-control" /></td>
                <td><input type="text" name="{name}_value[]" value="{val}" class="form-control" /></td>
            </tr>
            """

        # Render the table
        table_html = f"""
        <table class="table">
            <thead>
                <tr>
                    <th>Key</th>
                    <th>Value</th>
                </tr>
            </thead>
            <tbody>
                {rows}
                <tr>
                    <td><input type="text" name="{name}_key[]" class="form-control" /></td>
                    <td><input type="text" name="{name}_value[]" class="form-control" /></td>
                </tr>
            </tbody>
        </table>
        <input type="hidden" name="{name}" value='{json.dumps(value)}' />
        """
        return mark_safe(table_html)

    def value_from_datadict(self, data, files, name):
        # Reconstruct JSON from key-value pairs
        keys = data.getlist(f"{name}_key[]")
        values = data.getlist(f"{name}_value[]")
        return json.dumps({k: v for k, v in zip(keys, values) if k})


# class NewsletterForm(forms.ModelForm):
#     class Meta:
#         model = Newsletter
#         fields = '__all__'
#         widgets = {
#             'context': JSONEditor(),  # Assign the custom widget
#         }


def requeue_failed(modeladmin, request, queryset):
    for newsletter in queryset:
        EmailModel.objects.filter(newsletter=newsletter, status=STATUS.failed).update(status=STATUS.queued)


requeue_failed.short_description = 'Requeue failed emails'


def recreate(modeladmin, request, queryset):
    for newsletter in queryset.prefetch_related('attachments'):
        instance_data = {}
        attachments = newsletter.attachments.all()
        for field in newsletter._meta.get_fields():
            if not field.auto_created and not field.name == 'attachments':
                instance_data[field.name] = getattr(newsletter, field.name)

        newsletter.delete()

        instance_data['sent_emails'] = 0
        instance_data['failed_emails'] = 0
        instance_data['total_emails'] = 0
        instance_data['status'] = NewsletterStatus.draft

        new_instance = modeladmin.model.objects.create(**instance_data)
        new_instance.attachments.set(attachments)
        new_instance.save()


recreate.short_description = 'Recreate the newsletter'


@admin.register(Newsletter)
class NewsletterAdmin(admin.ModelAdmin):
    list_display = ('name', 'to_recipients', 'status', 'total_emails', 'sent_emails', 'failed_emails',)
    filter_horizontal = ['attachments']
    actions = [requeue_failed, recreate]
    formfield_overrides = {
        JSONField: {'widget': JSONEditor},
    }
    # form = NewsletterForm

    # def get_queryset(self, request):
    #     # Annotate the queryset with email status counts
    #     qs = super().get_queryset(request).annotate(
    #         total_emails=Count('emailmodel'),
    #         sent_emails=Count(Case(When(emailmodel__status=STATUS.sent, then=1), output_field=IntegerField())),
    #         failed_emails=Count(Case(When(emailmodel__status=STATUS.failed, then=1), output_field=IntegerField())),
    #         requeued_emails=Count(Case(When(emailmodel__status=STATUS.requeued, then=1), output_field=IntegerField())),
    #         queued_emails=Count(Case(When(emailmodel__status=STATUS.queued, then=1), output_field=IntegerField())),
    #     )
    #     return qs

    # def total_emails(self, obj):
    #     return obj.total_emails
    #
    # total_emails.short_description = 'Total Emails'

    # def sent_emails(self, obj):
    #     return obj.sent_emails
    #
    # sent_emails.short_description = 'Sent Emails'
    #
    # def failed_emails(self, obj):
    #     return obj.failed_emails
    #
    # failed_emails.short_description = 'Failed Emails'

    # def requeued_emails(self, obj):
    #     return obj.requeued_emails
    #
    # requeued_emails.short_description = 'Requeued Emails'
    #
    # def queued_emails(self, obj):
    #     return obj.queued_emails
    #
    # queued_emails.short_description = 'Queued Emails'

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context['send_newsletter_button'] = format_html(
            '''
            <input type="submit" value="Send" name="_send_many" style="background-color: var(--message-success-bg)"/>
            '''
        )
        return super().change_view(request, str(object_id), form_url=form_url, extra_context=extra_context)

    def response_change(self, request, obj):
        if "_send_many" in request.POST:
            obj.create()

        return super().response_change(request, obj)
