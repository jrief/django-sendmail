from functools import cached_property

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Count, Case, When, IntegerField

from sendmail.models import EmailMergeModel
from sendmail.parser import extract_variable_names, get_ckeditor_variables, get_custom_vars
from sendmail.validators import validate_email_with_name
from django.utils.translation import gettext_lazy as _
from sendmail.models.recipients_list import RecipientsList
from sendmail.models.emailmodel import PRIORITY
from sendmail.models.attachment import Attachment
from sendmail.models.emailmodel import EmailModel, STATUS
from sendmail import mail


class Newsletter(models.Model):
    PRIORITY_CHOICES = [
        (PRIORITY.low, _('low')),
        (PRIORITY.medium, _('medium')),
        (PRIORITY.high, _('high')),
        (PRIORITY.now, _('now')),
    ]

    name = models.CharField(_('Newsletter name'),
                            max_length=255,
                            unique=True)

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

    emailmerge = models.ForeignKey(
        EmailMergeModel,
        blank=True,
        null=True,
        verbose_name=_('EmailMergeModel'),
        on_delete=models.SET_NULL
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

    emails = models.ManyToManyField(EmailModel, editable=False, verbose_name=_('Emails'), related_name='emails')

    def __str__(self):
        return self.name

    def construct_default_json(self):
        if self.emailmerge:
            vars = extract_variable_names(self.emailmerge.template_file)
            vars.extend(get_ckeditor_variables(self.emailmerge))
        else:
            vars = get_custom_vars(self.subject)
            vars.extend(get_custom_vars(self.message))
            vars.extend(get_custom_vars(self.html_message))

        vars = list(set(vars))

        # Filter out recipient context, It is not expected to be filled by user
        vars = filter(lambda x: not x.startswith('recipient'), vars)

        return {var: '' for var in vars}

    def create(self):
        kwargs = {
            'recipients': list(self.to_recipients.recipients.all()),
            'sender': self.email_from,
            'priority': self.priority,
            'template': self.emailmerge,
            'context': self.context,
            'html_message': self.html_message,
            'subject': self.subject,
            'message': self.message,
            'language': self.language,
            'scheduled_time': self.scheduled_time,
            'expires_at': self.expires_at,
            'attachments': self.attachments.all()
        }
        emails = mail.send_many(**kwargs)
        self.emails.set(emails)


    def clean(self):
        if self.emailmerge and self.subject:
            raise ValidationError("Subject and emailmerge are mutually exclusive")

        if self.emailmerge and self.message:
            raise ValidationError("Message and emailmerge are mutually exclusive")

        if self.emailmerge and self.html_message:
            raise ValidationError("HTML message and emailmerge are mutually exclusive")

        super().clean()

    def save(self, *args, **kwargs):
        if not self.context:
            self.context = self.construct_default_json()

        super().save(*args, **kwargs)

    class Meta:
        app_label = 'sendmail'
        verbose_name = _('Newsletter')
        verbose_name_plural = _('Newsletters')
