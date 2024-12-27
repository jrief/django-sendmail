from django.contrib import admin
from django.db.models.fields.json import JSONField
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from sendmail.admin.admin_utils import get_language_name
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
    for newsletter in queryset:
        modeladmin.recreate(newsletter)


recreate.short_description = 'Recreate the newsletter'


@admin.register(Newsletter)
class NewsletterAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'to_recipients', 'status', 'result', 'total_emails', 'queued_emails', 'sent_emails', 'failed_emails',)
    actions = [requeue_failed, recreate]
    formfield_overrides = {
        JSONField: {'widget': JSONEditor},
    }

    list_filter = ['status', 'result']



    def get_fieldsets(self, request, obj = None):
        fieldsets = [
            (None, {
                'fields': ('name', 'emailmerge', 'to_recipients', 'email_from', 'language'),
            }),
            (_('Schedule'), {
                'fields': ('scheduled_time', 'expires_at', 'priority'),
                'classes': ('collapse',)
            }),
            (_('Context'), {
                'fields': ('context',),
                'classes': ('collapse',),
            }),
            (_('Headers'), {
                'fields': ('headers',),
                'classes': ('collapse',),
            }),
        ]

        if not self.has_change_permission(request, obj) and obj:
            fields = ['status', 'result', 'total_emails', 'sent_emails', 'failed_emails',
                           'queued_emails',]
            if get_tracking_enabled():
                fields.extend(['opened', 'clicked'])

            fieldsets.append((_('Result'), {
                'fields': fields,
                              'classes': ('collapse',)
            }))

        return fieldsets

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        if db_field.name == 'language':
            obj_id = request.resolver_match.kwargs.get('object_id')

            if obj_id:
                emailmerge = Newsletter.objects.get(pk=obj_id).emailmerge
                choices = [(None, '----------')]
                available_languages = [(lang, get_language_name(lang))
                                       for lang in emailmerge.get_available_languages()]

                choices.extend(available_languages)


                kwargs['choices'] = choices

        return super().formfield_for_choice_field(db_field, request, **kwargs)

    def get_list_display(self, request):
        list_display = (
            'name', 'to_recipients', 'status', 'result', 'total_emails', 'queued_emails', 'sent_emails',
            'failed_emails',)

        if get_tracking_enabled():
            list_display += ('opened', 'open_rate', 'clicked', 'click_rate',)

        return list_display

    def opened(self, obj):
        return EmailModel.objects.filter(opened_at__isnull=False, newsletter=obj).count()

    opened.short_description = _('Opened')

    def clicked(self, obj):
        return EmailModel.objects.filter(clicked_at__isnull=False, newsletter=obj).count()

    clicked.short_description = _('Clicked')

    def click_rate(self, obj):
        if not obj.sent_emails:
            return 0

        return self.clicked(obj) / obj.sent_emails

    def open_rate(self, obj):
        if not obj.sent_emails:
            return 0

        return self.opened(obj) / obj.sent_emails

    def recreate(self, obj):
        instance_data = {}
        for field in obj._meta.get_fields():
            if not field.auto_created:
                instance_data[field.name] = getattr(obj, field.name)

        obj.delete()

        instance_data['sent_emails'] = 0
        instance_data['failed_emails'] = 0
        instance_data['total_emails'] = 0
        instance_data['status'] = NewsletterStatus.draft
        instance_data['result'] = None

        new_instance = Newsletter.objects.create(**instance_data)
        new_instance.save()

        return new_instance

    def has_change_permission(self, request, obj=None):
        return obj and obj.status == NewsletterStatus.draft


    def queued_emails(self, obj):
        return EmailModel.objects.filter(newsletter=obj, status=STATUS.queued).count()

    queued_emails.short_description = _('Queued Emails')

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        can_send = False
        if object_id:
            obj = Newsletter.objects.get(pk=object_id)
            if obj.status == NewsletterStatus.draft:
                can_send = True

        extra_context['show_newsletter_send'] = can_send
        extra_context['show_reparse'] = can_send
        return super().change_view(request, str(object_id), form_url=form_url, extra_context=extra_context)

    def response_change(self, request, obj):
        if "_send_many" in request.POST:
            obj.create()

        if "_reparse" in request.POST:
            obj.reparse_context()
            return redirect(
                reverse(
                    'admin:%s_%s_change' % (self.model._meta.app_label, self.model._meta.model_name),
                    args=[obj.pk]
                ))

        return super().response_change(request, obj)
