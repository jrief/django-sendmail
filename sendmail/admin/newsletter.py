from django.contrib import admin
from django.db.models.fields.json import JSONField

from sendmail.models.emailmodel import STATUS, EmailModel
from sendmail.models.newsletter import RESULT
from sendmail.models.newsletter import STATUS as NewsletterStatus
from sendmail.models.newsletter import Newsletter
from sendmail.settings import get_tracking_enabled

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

    def get_list_display(self, request):
        list_display = (
            'name', 'to_recipients', 'status', 'result', 'total_emails', 'queued_emails', 'sent_emails',
            'failed_emails',)

        if get_tracking_enabled():
            list_display += ('opened', 'open_rate', 'clicked', 'click_rate',)

        return list_display

    def opened(self, obj):
        return EmailModel.objects.filter(opened_at__isnull=False, newsletter=obj).count()

    def clicked(self, obj):
        return EmailModel.objects.filter(clicked_at__isnull=False, newsletter=obj).count()

    def click_rate(self, obj):
        if not obj.sent_emails:
            return 0

        return self.clicked(obj) / obj.sent_emails

    def open_rate(self, obj):
        if not obj.sent_emails:
            return 0

        return self.opened(obj) / obj.sent_emails

    def has_change_permission(self, request, obj=None):
        return obj and obj.status == NewsletterStatus.draft


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
