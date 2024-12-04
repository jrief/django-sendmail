from collections import namedtuple

from django.core.exceptions import ValidationError
from django.db import models

from sendmail.models.emailmerge import EmailMergeModel
from sendmail.parser import extract_variable_names, get_ckeditor_variables, get_custom_vars
from sendmail.validators import validate_email_with_name
from django.utils.translation import gettext_lazy as _
from sendmail.models.recipients_list import RecipientsList
from sendmail.models.attachment import Attachment
from sendmail import mail

STATUS = namedtuple('STATUS', 'draft creation queued completed')._make(range(4))
PRIORITY = namedtuple('PRIORITY', 'low medium high now')._make(range(4))
RESULT = namedtuple('RESULT', 'failed success partial')._make(range(3))


class Newsletter(models.Model):
    PRIORITY_CHOICES = [
        (PRIORITY.low, _('low')),
        (PRIORITY.medium, _('medium')),
        (PRIORITY.high, _('high')),
        (PRIORITY.now, _('now')),
    ]

    STATUS_CHOICES = [
        (STATUS.draft, _('draft')),
        (STATUS.creation, _('creation')),
        (STATUS.queued, _('queued')),
        (STATUS.completed, _('completed')),
    ]

    RESULT_CHOICES = [
        (RESULT.failed, _('all failed')),
        (RESULT.success, _('all successful')),
        (RESULT.partial, _('partially successful')),
    ]

    name = models.CharField(_('Newsletter name'),
                            max_length=255,
                            unique=True)

    status = models.PositiveSmallIntegerField(_('Status'),
                                              choices=STATUS_CHOICES,
                                              db_index=True,
                                              default=STATUS.draft,
                                              editable=False)

    result = models.PositiveSmallIntegerField(_('Result'),
                                              choices=RESULT_CHOICES,
                                              db_index=True,
                                              null=True,
                                              blank=True,
                                              editable=False)

    created = models.DateTimeField(auto_now_add=True,
                                   db_index=True)

    priority = models.PositiveSmallIntegerField(_('Priority'), choices=PRIORITY_CHOICES, blank=True, null=True)

    email_from = models.CharField(_('From email'),
                                  max_length=255,
                                  validators=[validate_email_with_name],
                                  blank=True,
                                  null=True)

    to_recipients = models.ForeignKey(RecipientsList,
                                      verbose_name=_('To recipients'),
                                      on_delete=models.CASCADE, )

    language = models.CharField(_('Force to Language'),
                                max_length=12,
                                null=True,
                                blank=True,
                                choices=[])

    scheduled_time = models.DateTimeField(
        _('Scheduled Time'), blank=True, null=True, db_index=True, help_text=_('The scheduled sending time')
    )

    expires_at = models.DateTimeField(
        _('Expires'), blank=True, null=True, help_text=_("Email won't be sent after this timestamp")
    )

    subject = models.CharField(_('Subject'), max_length=989, blank=True)
    message = models.TextField(_('Message'), blank=True)
    html_message = models.TextField(_('HTML Message'), blank=True)
    headers = models.JSONField(_('Headers'), blank=True, null=True)

    emailmerge = models.ForeignKey(
        EmailMergeModel,
        blank=True,
        null=True,
        verbose_name=_('EmailMerge'),
        on_delete=models.SET_NULL,
        help_text=_('Changing this erases existing context')
    )

    context = models.JSONField(_('Context'),
                               blank=True,
                               null=True)

    attachments = models.ManyToManyField(
        Attachment,
        related_name='attachments',
        verbose_name=_('Attachments'),
        blank=True,
    )

    total_emails = models.PositiveSmallIntegerField(_('Total Emails'), default=0, editable=False)
    sent_emails = models.PositiveSmallIntegerField(_('Sent Emails'), default=0, editable=False)
    failed_emails = models.PositiveSmallIntegerField(_('Failed Emails'), default=0, editable=False)

    #emails = models.ManyToManyField(EmailModel, editable=False, verbose_name=_('Emails'), related_name='emails')

    def __str__(self):
        return self.name

    def construct_default_json(self):
        if self.emailmerge:
            vars = extract_variable_names(self.emailmerge.template_file)
            ckeditor_vars = get_ckeditor_variables(self.emailmerge)
            vars = {**vars, **{var: '' for var in ckeditor_vars}}
        else:
            vars = get_custom_vars(self.subject)
            vars.extend(get_custom_vars(self.message))
            vars.extend(get_custom_vars(self.html_message))
            vars = list(set(vars))
            vars = filter(lambda x: not x.startswith('recipient'), vars)
            vars = {var: '' for var in vars}

        # Filter out recipient context, It is not expected to be filled by user

        return vars

    def check_status(self):
        self.refresh_from_db()
        if (self.sent_emails + self.failed_emails) == self.total_emails:
            self.status = STATUS.completed

            if self.sent_emails == self.total_emails:
                self.result = RESULT.success
            elif self.failed_emails == self.total_emails:
                self.result = RESULT.failed
            else:
                self.result = RESULT.partial

            self.save()

    def create(self):
        self.status = STATUS.creation
        self.save()
        kwargs = {
            'recipients': list(self.to_recipients.recipients.all()),
            'sender': self.email_from,
            'priority': self.priority,
            'emailmerge': self.emailmerge,
            'context': self.context,
            'html_message': self.html_message,
            'subject': self.subject,
            'message': self.message,
            'language': self.language,
            'scheduled_time': self.scheduled_time,
            'expires_at': self.expires_at,
            'attachments': self.attachments.all(),
            'headers': dict(self.headers or {}),
            'newsletter': self,
        }
        emails = mail.send_many(**kwargs)

        self.total_emails = len(emails)
        self.status = STATUS.queued
        self.save()

        return emails

    def clean(self):
        if self.emailmerge and self.subject:
            raise ValidationError("Subject and emailmerge are mutually exclusive")

        if self.emailmerge and self.message:
            raise ValidationError("Message and emailmerge are mutually exclusive")

        if self.emailmerge and self.html_message:
            raise ValidationError("HTML message and emailmerge are mutually exclusive")

        super().clean()

    def save(self, *args, **kwargs):
        if self.pk:
            old_instance = Newsletter.objects.get(pk=self.pk)
            if old_instance.emailmerge != self.emailmerge:
                self.context = None
        if not self.context:
            self.context = self.construct_default_json()

        super().save(*args, **kwargs)

    class Meta:
        app_label = 'sendmail'
        verbose_name = _('Newsletter')
        verbose_name_plural = _('Newsletters')
