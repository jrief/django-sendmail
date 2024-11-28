from django.contrib import admin
from django.utils.html import format_html
from sendmail.models.emailmodel import STATUS, EmailModel
from sendmail.models.newsletter import Newsletter, STATUS as NewsletterStatus, RESULT

from django.db.models.fields.json import JSONField

from django import forms
from django.utils.safestring import mark_safe
import json

try:
    from jsoneditor.forms import JSONEditor
except ImportError:
    JSONEditor = None


def requeue_failed(modeladmin, request, queryset):
    queryset = queryset.filter(status=NewsletterStatus.completed, result__in=[RESULT.failed, RESULT.partial])
    for newsletter in queryset:
        EmailModel.objects.filter(newsletter=newsletter, status=STATUS.failed).update(status=STATUS.queued)
    queryset.update(failed_emails=0, status=NewsletterStatus.queued, result=None)


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
        instance_data['result'] = None

        new_instance = modeladmin.model.objects.create(**instance_data)
        new_instance.attachments.set(attachments)
        new_instance.save()


recreate.short_description = 'Recreate the newsletter'


@admin.register(Newsletter)
class NewsletterAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'to_recipients', 'status', 'result', 'total_emails', 'queued_emails', 'sent_emails', 'failed_emails',)
    filter_horizontal = ['attachments']
    actions = [requeue_failed, recreate]
    formfield_overrides = {
        JSONField: {'widget': JSONEditor},
    }

    list_filter = ['status', 'result']

    def has_change_permission(self, request, obj=None):
        return obj and obj.status == NewsletterStatus.draft


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
    def queued_emails(self, obj):
        return EmailModel.objects.filter(newsletter=obj, status=STATUS.queued).count()

    queued_emails.short_description = 'Queued Emails'

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        can_send = False
        if object_id:
            obj = Newsletter.objects.get(pk=object_id)
            if obj.status == NewsletterStatus.draft:
                can_send = True

        extra_context['show_newsletter_send'] = can_send
        return super().change_view(request, str(object_id), form_url=form_url, extra_context=extra_context)

    def response_change(self, request, obj):
        if "_send_many" in request.POST:
            obj.create()

        return super().response_change(request, obj)
