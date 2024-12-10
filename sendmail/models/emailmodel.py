from collections import namedtuple
from email.mime.nonmultipart import MIMENonMultipart
from typing import Union

from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

from sendmail.connections import connections
from sendmail.logutils import setup_loghandlers
from sendmail.models.emailaddress import Recipient
from sendmail.sanitizer import clean_html
from sendmail.settings import get_email_address_model, get_email_address_setting, get_log_level, get_template_engine
from sendmail.validators import validate_email_with_name

logger = setup_loghandlers('INFO')

PRIORITY = namedtuple('PRIORITY', 'low medium high now')._make(range(4))
STATUS = namedtuple('STATUS', 'sent failed queued requeued')._make(range(4))


class EmailModel(models.Model):
    """
    A model to hold email information.
    """

    PRIORITY_CHOICES = [
        (PRIORITY.low, _('low')),
        (PRIORITY.medium, _('medium')),
        (PRIORITY.high, _('high')),
        (PRIORITY.now, _('now')),
    ]
    STATUS_CHOICES = [
        (STATUS.sent, _('sent')),
        (STATUS.failed, _('failed')),
        (STATUS.queued, _('queued')),
        (STATUS.requeued, _('requeued')),
    ]

    from_email = models.CharField(_('Email From'), max_length=254, validators=[validate_email_with_name])
    recipients = models.ManyToManyField(get_email_address_setting(), related_name='to_emails', through=Recipient)
    subject = models.CharField(_('Subject'), max_length=989, blank=True)
    message = models.TextField(_('Message'), blank=True)
    html_message = models.TextField(_('HTML Message'), blank=True)
    """
    Emails with 'queued' status will get processed by ``send_queued`` command.
    Status field will then be set to ``failed`` or ``sent`` depending on
    whether it's successfully delivered.
    """
    status = models.PositiveSmallIntegerField(_('Status'), choices=STATUS_CHOICES, db_index=True, blank=True, null=True)
    priority = models.PositiveSmallIntegerField(_('Priority'), choices=PRIORITY_CHOICES, blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    last_updated = models.DateTimeField(db_index=True, auto_now=True)
    scheduled_time = models.DateTimeField(
        _('Scheduled Time'), blank=True, null=True, db_index=True, help_text=_('The scheduled sending time')
    )
    expires_at = models.DateTimeField(
        _('Expires'), blank=True, null=True, help_text=_("Email won't be sent after this timestamp")
    )
    opened_at = models.DateTimeField(
        _('Opened'), blank=True, null=True, help_text=_("Email opening time")
    )
    clicked_at = models.DateTimeField(
        _('Clicked'), blank=True, null=True, help_text=_("Email first click time")
    )
    message_id = models.CharField('Message-ID', null=True, max_length=255, editable=False)
    number_of_retries = models.PositiveIntegerField(null=True, blank=True)
    headers = models.JSONField(_('Headers'), blank=True, null=True)
    template = models.ForeignKey(
        'sendmail.EmailMergeModel', blank=True, null=True, verbose_name=_('EmailMergeModel'), on_delete=models.CASCADE
    )
    language = models.CharField(max_length=12)
    context = models.JSONField(_('Context'), blank=True, null=True)
    backend_alias = models.CharField(_('Backend alias'), blank=True, default='', max_length=64)
    newsletter = models.ForeignKey('sendmail.Newsletter', on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        app_label = 'sendmail'
        verbose_name = pgettext_lazy('Email address', 'Email')
        verbose_name_plural = pgettext_lazy('Email addresses', 'Emails')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cached_email_message = None

    def __str__(self):
        return str([str(recipient) for recipient in self.recipients.all()])

    def get_message_object(self,
                           html_message,
                           plaintext_message,
                           headers,
                           subject,
                           connection,
                           multipart_template) \
            -> Union[EmailMessage, EmailMultiAlternatives]:
        to_list = [str(to) for to in self.recipients.through.objects.filter(email=self, send_type='to')]
        cc_list = [str(cc) for cc in self.recipients.through.objects.filter(email=self, send_type='cc')]
        bcc_list = [str(bcc) for bcc in self.recipients.through.objects.filter(email=self, send_type='bcc')]
        common_args = {
            'subject': subject,
            'from_email': self.from_email,
            'to': to_list,
            'bcc': bcc_list,
            'cc': cc_list,
            'headers': headers,
            'connection': connection,
        }
        if html_message:

            msg = EmailMultiAlternatives(body=plaintext_message or html_message, **common_args)

            if multipart_template:
                html_message = multipart_template.render({'dry_run': False})
                msg.body = plaintext_message or html_message
            if plaintext_message:
                msg.attach_alternative(html_message, 'text/html')
            else:
                msg.content_subtype = 'html'

            if multipart_template:
                multipart_template.attach_related(msg)
        else:
            msg = EmailMessage(body=plaintext_message, **common_args)

        return msg

    def email_message(self):
        """
        Returns Django EmailMessage object for sending.
        """
        if self._cached_email_message:
            return self._cached_email_message

        return self.prepare_email_message()

    def prepare_email_message(self):
        """
        Returns a django ``EmailMessage`` or ``EmailMultiAlternatives`` object,
        depending on whether html_message is empty.
        """

        # Replace recipient id with EmailAddress object
        if self.context:
            context = {**self.context}
            context['recipient'] = get_email_address_model().objects.get(id=self.context['recipient'])
        else:
            context = {}

        if self.newsletter:
            context.update({'email_id': self.id})

        subject = render_message(self.subject, context)
        plaintext_message = render_message(self.message, context)

        if self.template is not None and self.context is not None:
            html_message = self.template.render_email_template(recipient=context['recipient'],
                                                               language=self.language,
                                                               context_dict=context)
            html_message = render_message(html_message, context)

            engine = get_template_engine()
            multipart_template = engine.from_string(html_message)

        else:
            multipart_template = None
            html_message = render_message(self.html_message, context)

        connection = connections[self.backend_alias or 'default']
        if isinstance(self.headers, dict) or self.expires_at or self.message_id:
            headers = dict(self.headers or {})
            if self.expires_at:
                headers.update({'Expires': self.expires_at.strftime('%a, %-d %b %H:%M:%S %z')})
            if self.message_id:
                headers.update({'Message-ID': self.message_id})
        else:
            headers = None

        msg = self.get_message_object(html_message=html_message,
                                      plaintext_message=plaintext_message,
                                      headers=headers,
                                      subject=subject,
                                      connection=connection,
                                      multipart_template=multipart_template)

        for attachment in self.attachments.all():
            attachment.file.open('rb')
            if attachment.headers:
                mime_part = MIMENonMultipart(*attachment.mimetype.split('/'))
                mime_part.set_payload(attachment.file.read())
                for key, val in attachment.headers.items():
                    try:
                        mime_part.replace_header(key, val)
                    except KeyError:
                        mime_part.add_header(key, val)
                msg.attach(mime_part)
            else:
                msg.attach(attachment.name, attachment.file.read(), mimetype=attachment.mimetype or None)
            attachment.file.close()

        self._cached_email_message = msg
        return msg

    def dispatch(self, log_level=None, disconnect_after_delivery=True, commit=True):
        """
        Sends email and log the result.
        """
        try:
            self.email_message().send()
            status = STATUS.sent
            message = ''
            exception_type = ''
        except Exception as e:
            status = STATUS.failed
            message = str(e)
            exception_type = type(e).__name__
            if commit:
                logger.exception('Failed to send email')
            else:
                # If run in a bulk sending mode, re-raise and let the outer
                # layer handle the exception
                raise

        if disconnect_after_delivery:
            connections.close()

        if commit:
            self.status = status
            self.save(update_fields=['status'])

            if log_level is None:
                log_level = get_log_level()

            # If log level is 0, log nothing, 1 logs only sending failures
            # and 2 means log both successes and failures
            if log_level == 1:
                if status == STATUS.failed:
                    self.logs.create(status=status, message=message, exception_type=exception_type)
            elif log_level == 2:
                self.logs.create(status=status, message=message, exception_type=exception_type)

        return status

    def clean(self):
        if self.scheduled_time and self.expires_at and self.scheduled_time > self.expires_at:
            raise ValidationError(_('The scheduled time may not be later than the expires time.'))

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


def render_message(html_str, context):
    """
    Replaces variables of format #var# with actual values from the context.
    Fills recipient data into added placeholders.
    """
    for placeholder, value in context.items():
        placeholder_notation = f"#{placeholder}#"
        html_str = html_str.replace(placeholder_notation, clean_html(str(value)))

    if recipient := context.get('recipient', None):
        for field in recipient._meta.get_fields():
            if field.concrete:
                placeholder_notation = f"#recipient.{field.name}#"
                value = getattr(recipient, field.name, "")
                html_str = html_str.replace(placeholder_notation, clean_html(str(value)))

    return html_str
