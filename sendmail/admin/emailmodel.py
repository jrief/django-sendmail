import re

from django.contrib import admin, messages
from django.core.mail import SafeMIMEText
from django.http import HttpResponse, HttpResponseNotFound, HttpResponseRedirect
from django.urls import re_path, reverse
from django.utils.html import format_html
from django.utils.text import Truncator
from django.utils.translation import gettext_lazy as _

from sendmail.admin.attachment import AttachmentInline
from sendmail.admin.emailaddress import RecipientInline
from sendmail.admin.log import LogInline
from sendmail.models.emailmodel import STATUS, EmailModel
from sendmail.sanitizer import clean_html
from sendmail.settings import get_tracking_enabled


def requeue(modeladmin, request, queryset):
    """An admin action to requeue emails."""
    queryset.update(status=STATUS.queued)


requeue.short_description = 'Requeue selected emails'



@admin.register(EmailModel)
class EmailAdmin(admin.ModelAdmin):


    def get_list_display(self, request):
        list_display = [
            'truncated_message_id',
            # 'to_display',
            'shortened_subject',
            'status',
            'last_updated',
            'scheduled_time',
            'use_template',
            'newsletter',
        ]
        if get_tracking_enabled():
            list_display.extend(['opened_at', 'clicked_at'])

        return list_display

    search_fields = ['message_id', 'subject']
    readonly_fields = ['message_id', 'language', 'render_subject', 'render_plaintext_body', 'render_html_body']
    inlines = [RecipientInline, AttachmentInline, LogInline, ]
    list_filter = ['status', 'template__name', 'newsletter']
    actions = [requeue]

    def get_urls(self):
        urls = [
            re_path(
                r'^(?P<pk>\d+)/image/(?P<content_id>[0-9a-f]{32})$',
                self.fetch_email_image,
                name='sendmail_email_image',
            ),
            re_path(r'^(?P<pk>\d+)/resend/$', self.resend, name='resend'),
        ]
        urls.extend(super().get_urls())
        return urls

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('template')

    def to_display(self, instance):
        return ', '.join([str(to) for to in instance.to])

    def truncated_message_id(self, instance):
        if instance.message_id:
            return Truncator(instance.message_id[1:-1]).chars(10)
        return str(instance.id)

    to_display.short_description = _('To')
    to_display.admin_order_field = 'to'
    truncated_message_id.short_description = 'Message-ID'

    def has_add_permission(self, request):
        return False

    def shortened_subject(self, instance):
        subject = instance.subject
        return Truncator(subject).chars(100)

    shortened_subject.short_description = _('Subject')
    shortened_subject.admin_order_field = 'subject'

    def use_template(self, instance):
        return bool(instance.template_id)

    use_template.short_description = _('Use Template')
    use_template.boolean = True

    def get_fieldsets(self, request, obj=None):
        fields = ['from_email', 'priority', ('status', 'scheduled_time')]
        if obj.message_id:
            fields.insert(0, 'message_id')
        fieldsets = [(None, {'fields': fields})]
        has_plaintext_content, has_html_content = False, False
        try:
            for part in obj.email_message().message().walk():
                if not isinstance(part, SafeMIMEText):
                    continue
                content_type = part.get_content_type()
                if content_type == 'text/plain':
                    has_plaintext_content = True
                elif content_type == 'text/html':
                    has_html_content = True
        except Exception as e:
            has_plaintext_content = True

        if has_html_content:
            fieldsets.append((_('HTML Email'), {'fields': ['render_subject', 'render_html_body']}))
            if has_plaintext_content:
                fieldsets.append((_('Text Email'), {'classes': ['collapse'], 'fields': ['render_plaintext_body']}))
        elif has_plaintext_content:
            fieldsets.append((_('Text Email'), {'fields': ['render_subject', 'render_plaintext_body']}))

        return fieldsets

    def render_subject(self, instance):
        try:
            message = instance.email_message()
            return message.subject
        except Exception:
            return "Rendering exception"

    render_subject.short_description = _('Subject')

    def render_plaintext_body(self, instance):
        try:
            for message in instance.email_message().message().walk():
                if isinstance(message, SafeMIMEText) and message.get_content_type() == 'text/plain':
                    return format_html('<pre>{}</pre>', message.get_payload())
        except Exception as e:
            return format_html('<pre>{}</pre>', f"Rendering failed: {str(e)}")

    render_plaintext_body.short_description = _('Mail Body')

    def render_html_body(self, instance):
        re.compile('cid:([0-9a-f]{32})')
        url = reverse('admin:sendmail_email_image', kwargs={'pk': instance.id, 'content_id': 32 * '0'})
        url.replace(32 * '0', r'\1')
        try:
            for message in instance.email_message().message().walk():
                if isinstance(message, SafeMIMEText) and message.get_content_type() == 'text/html':
                    payload = message.get_payload(decode=True).decode('utf-8')
                    return clean_html(payload)
        except Exception as e:
            return format_html('<pre>{}</pre>', f"Rendering failed: {str(e)}")

    render_html_body.short_description = _('HTML Body')

    def fetch_email_image(self, request, pk, content_id):
        instance = self.get_object(request, pk)
        for message in instance.email_message().message().walk():
            if message.get_content_maintype() == 'image' and message.get('Content-Id')[1:33] == content_id:
                return HttpResponse(message.get_payload(decode=True), content_type=message.get_content_type())
        return HttpResponseNotFound()

    def resend(self, request, pk):
        instance = self.get_object(request, pk)
        instance.dispatch()
        messages.info(request, 'Email has been sent again')
        return HttpResponseRedirect(reverse('admin:sendmail_email_change', args=[instance.pk]))
