import os
from collections import namedtuple
from typing import Union
from uuid import uuid4
from email.mime.nonmultipart import MIMENonMultipart
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.db import models
from django.utils.translation import pgettext_lazy, gettext_lazy as _
from django.utils import timezone
from ckeditor_uploader.fields import RichTextUploadingField
from sendmail import cache
from .cache_utils import get_placeholders
from django.conf import settings
from .connections import connections
from .logutils import setup_loghandlers
from .parser import process_template
from .sanitizer import clean_html
from .settings import get_log_level, get_template_engine, get_languages_list, get_attachments_storage
from .validators import validate_email_with_name, validate_template_syntax
from django.template import loader

logger = setup_loghandlers('INFO')

PRIORITY = namedtuple('PRIORITY', 'low medium high now')._make(range(4))
STATUS = namedtuple('STATUS', 'sent failed queued requeued')._make(range(4))


class Recipient(models.Model):
    """
    Map table for storing ManyToMany relationships between users and emails.
    """
    SEND_TYPES = [
        ('to', _('To')),
        ('cc', _('Cc')),
        ('bcc', _('Bcc')),
    ]
    email = models.ForeignKey('sendmail.EmailModel', on_delete=models.CASCADE)
    address = models.ForeignKey('sendmail.EmailAddress', on_delete=models.CASCADE)
    send_type = models.CharField(max_length=12, choices=SEND_TYPES, default='to')

    def __str__(self):
        return self.address.email

    class Meta:
        app_label = 'sendmail'


class EmailAddress(models.Model):
    """
    A model to hold Email recipient information.
    """
    GENDERS = [
        ('male', _('Male')),
        ('female', _('Female')),
        ('other', _('Other')),
    ]
    email = models.CharField(_('Email From'),
                             max_length=254,
                             validators=[validate_email_with_name],
                             unique=True)
    first_name = models.CharField(_('First Name'), max_length=254, blank=True, null=True)
    last_name = models.CharField(_('Last Name'), max_length=254, blank=True, null=True)
    gender = models.CharField(_('Gender'), max_length=15, blank=True, null=True, choices=GENDERS)
    preferred_language = models.CharField(
        max_length=12,
        verbose_name=_('Language'),
        help_text=_('Users preferred language'),
        default='',
        blank=True,
    )
    is_blocked = models.BooleanField(_('Is blocked'), default=False)

    def __str__(self):
        return self.email

    class Meta:
        app_label = 'sendmail'


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
    recipients = models.ManyToManyField(EmailAddress, related_name='to_emails', through=Recipient)
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
    message_id = models.CharField('Message-ID', null=True, max_length=255, editable=False)
    number_of_retries = models.PositiveIntegerField(null=True, blank=True)
    headers = models.JSONField(_('Headers'), blank=True, null=True)
    template = models.ForeignKey(
        'sendmail.EmailMergeModel', blank=True, null=True, verbose_name=_('EmailMergeModel'), on_delete=models.CASCADE
    )
    language = models.CharField(max_length=12)
    context = models.JSONField(_('Context'), blank=True, null=True)
    backend_alias = models.CharField(_('Backend alias'), blank=True, default='', max_length=64)

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
        # if get_override_recipients():
        #     self.to = get_override_recipients()

        # Replace recipient id with EmailAddress object
        if self.context:
            context = {**self.context}
            context['recipient'] = EmailAddress.objects.get(id=self.context['recipient'])
        else:
            context = {}

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


class Log(models.Model):
    """
    A model to record sending email sending activities.
    """

    STATUS_CHOICES = [(STATUS.sent, _('sent')), (STATUS.failed, _('failed'))]

    email = models.ForeignKey(
        EmailModel, editable=False, related_name='logs', verbose_name=_('Email address'), on_delete=models.CASCADE
    )
    date = models.DateTimeField(auto_now_add=True)
    status = models.PositiveSmallIntegerField(_('Status'), choices=STATUS_CHOICES)
    exception_type = models.CharField(_('Exception type'), max_length=255, blank=True)
    message = models.TextField(_('Message'))

    class Meta:
        app_label = 'sendmail'
        verbose_name = _('Log')
        verbose_name_plural = _('Logs')

    def __str__(self):
        return str(self.date)


class EmailMergeModel(models.Model):
    """
    Model to hold template information from db
    """

    base_file = models.CharField(max_length=255, verbose_name=_('File name'))
    name = models.CharField(_('Name'), max_length=255, help_text=_("e.g: 'welcome_email'"), unique=True)
    description = models.TextField(_('Description'), blank=True, help_text=_('Description of this template.'))
    created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    extra_recipients = models.ManyToManyField(
        EmailAddress,
        blank=True,
        help_text='extra bcc recipients',
    )

    class Meta:
        app_label = 'sendmail'
        verbose_name = _('EmailMergeModel')
        verbose_name_plural = _('EmailMergeModels')
        ordering = ['name']

    def __str__(self):
        return self.name

    def render_email_template(self, language='', recipient=None, context_dict=None):
        """
        Function to render an email template. Takes an EmailAddress object.
        """
        if not language:
            raise
        if not context_dict:
            context_dict = {}

        engine = get_template_engine()
        context = {'recipient': recipient, 'dry_run': True, **context_dict} \
            if recipient else {'dry_run': True, **context_dict}

        django_template_first_pass = loader.get_template(self.base_file, using='sendmail')

        # Replace all {% placeholder <name> %} to {{ name }}
        first_pass_content = django_template_first_pass.render(context)

        placeholders = get_placeholders(self, language=language)
        context_data = {placeholder.placeholder_name: clean_html(placeholder.content) for placeholder in placeholders}
        context_data = {**context_data, 'dry_run': True}

        # Replaces placeholders with actual values
        django_template_second_pass = engine.from_string("{% load sendmail %}" + first_pass_content)
        final_content = django_template_second_pass.render(context_data)

        final_content = f"{{% load sendmail %}}\n {final_content}"

        return final_content

    def save(self, *args, **kwargs):
        template = super().save(*args, **kwargs)
        cache.delete(self.name)
        existing_languages = set(self.translated_contents.values_list('language', flat=True))
        for lang in set(get_languages_list()) - existing_languages:
            EmailMergeContentModel.objects.create(subject=f'Subject, language: {lang}',
                                                  content=f'Content, language: {lang}',
                                                  emailmerge=self,
                                                  language=lang
                                                  )

        placeholder_names = process_template(self.base_file)
        print(placeholder_names)

        existing_placeholders = set(
            self.contents.filter(base_file=self.base_file).values_list('placeholder_name',
                                                                       'language'))
        placeholder_objs = []
        for placeholder_name in placeholder_names:
            for lang in get_languages_list():
                if (placeholder_name, lang) not in existing_placeholders:
                    placeholder_objs.append(PlaceholderContent(placeholder_name=placeholder_name,
                                                               language=lang,
                                                               base_file=self.base_file,
                                                               emailmerge=self,
                                                               content=f"Placeholder: {placeholder_name}, "
                                                                       f"Language: {lang}", ), )

        PlaceholderContent.objects.bulk_create(placeholder_objs)

        return template


class EmailMergeContentModel(models.Model):
    emailmerge = models.ForeignKey(EmailMergeModel,
                                   related_name='translated_contents',
                                   on_delete=models.CASCADE)
    language = models.CharField(max_length=12)
    subject = models.CharField(max_length=255,
                               blank=True,
                               verbose_name=_('Subject'),
                               validators=[validate_template_syntax]
                               )
    content = models.TextField(blank=True,
                               verbose_name=_('Content'),
                               validators=[validate_template_syntax])
    extra_attachments = models.ManyToManyField('Attachment',
                                               related_name='extra_attachments',
                                               verbose_name=_('Extra Attachments'),
                                               blank=True,
                                               )

    def __str__(self):
        return f"{self.emailmerge.name}: {self.language}"

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['emailmerge', 'language'],
                                    name='unique_content'),
        ]
        app_label = 'sendmail'
        verbose_name = _('Email Template Content')
        verbose_name_plural = _('Email Template Contents')


def get_upload_path(instance, filename):
    """Overriding to store the original filename"""
    if not instance.name:
        instance.name = filename  # set original filename
    date = timezone.now().date()
    filename = '{name}.{ext}'.format(name=uuid4().hex, ext=filename.split('.')[-1])

    return os.path.join('sendmail_attachments', str(date.year), str(date.month), str(date.day), filename)


class Attachment(models.Model):
    """
    A model describing an email attachment.
    """

    file = models.FileField(_('File'), upload_to=get_upload_path, storage=get_attachments_storage)
    name = models.CharField(_('Name'), max_length=255, help_text=_('The original filename'))
    emails = models.ManyToManyField(EmailModel, related_name='attachments', verbose_name=_('Emails'), blank=True)
    mimetype = models.CharField(max_length=255, default='', blank=True)
    headers = models.JSONField(_('Headers'), blank=True, null=True)

    class Meta:
        app_label = 'sendmail'
        verbose_name = _('Attachment')
        verbose_name_plural = _('Attachments')

    def __str__(self):
        return self.name


class DBMutex(models.Model):
    lock_id = models.CharField(
        max_length=50,
        unique=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    expires_at = models.DateTimeField()

    locked_by = models.UUIDField(
        db_index=True,
    )

    def __str__(self):
        return f"<DBMutex(pk={self.pk}, lock_id={self.lock_id}>"


class PlaceholderContent(models.Model):
    emailmerge = models.ForeignKey(EmailMergeModel,
                                   on_delete=models.CASCADE,
                                   related_name='contents', )
    language = models.CharField(
        max_length=12,
        default='',
        blank=True,
        choices=settings.LANGUAGES,
    )
    placeholder_name = models.CharField(_('Placeholder name'),
                                        max_length=63, )
    content = RichTextUploadingField(_('Content'), default='')

    base_file = models.CharField(max_length=255, verbose_name=_('File name'))

    class Meta:
        app_label = 'sendmail'
        constraints = [
            models.UniqueConstraint(fields=['emailmerge', 'placeholder_name', 'language', 'base_file'],
                                    name='unique_placeholder'),
        ]

    def save(self, *args, **kwargs):
        cache.delete('placeholders %s:%s:%s' % (self.emailmerge.name, self.language, self.base_file))
        return super().save(*args, **kwargs)
