from collections import namedtuple

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from sendmail import mail
from sendmail.models.attachment import Attachment
from sendmail.models.emailmerge import EmailMergeModel
from sendmail.models.recipients_list import RecipientsList
from sendmail.parser import extract_variable_names, get_ckeditor_variables, get_custom_vars
from sendmail.validators import validate_email_with_name

STATUS = namedtuple('STATUS', 'draft creation queued completed')._make(range(4))
PRIORITY = namedtuple('PRIORITY', 'low medium high now')._make(range(4))
RESULT = namedtuple('RESULT', 'failed success partial')._make(range(3))


class Newsletter(models.Model):
    """
    Model that holds newsletter information.
    """
    PRIORITY_CHOICES = [
        (PRIORITY.low, _('low')),
        (PRIORITY.medium, _('medium')),
        (PRIORITY.high, _('high')),
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

    to_recipients = models.ForeignKey(RecipientsList,
                                      verbose_name=_('Recipients List'),
                                      on_delete=models.CASCADE, )

    emailmerge = models.ForeignKey(
        EmailMergeModel,
        verbose_name=_('EmailMerge'),
        on_delete=models.CASCADE,
    )

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


    language = models.CharField(_('Force to Language'),
                                max_length=12,
                                null=True,
                                blank=True,
                                choices=settings.LANGUAGES,
                                help_text='Set to None if you want to use recipients preferred language. ')

    scheduled_time = models.DateTimeField(
        _('Scheduled Time'), blank=True, null=True, db_index=True, help_text=_('The scheduled sending time')
    )

    expires_at = models.DateTimeField(
        _('Expires'), blank=True, null=True, help_text=_("Email won't be sent after this timestamp")
    )

    # subject = models.CharField(_('Subject'), max_length=989, blank=True)
    # message = models.TextField(_('Message'), blank=True)
    # html_message = models.TextField(_('HTML Message'), blank=True)
    headers = models.JSONField(_('Headers'), blank=True, null=True)


    context = models.JSONField(_('Context'),
                               blank=True,
                               null=True)


    total_emails = models.PositiveSmallIntegerField(_('Total Emails'), default=0, editable=False)
    sent_emails = models.PositiveSmallIntegerField(_('Sent Emails'), default=0, editable=False)
    failed_emails = models.PositiveSmallIntegerField(_('Failed Emails'), default=0, editable=False)


    def __str__(self):
        return self.name

    def check_status(self):
        """
        Updates the status and result of an email-sending operation based on the number
        of sent and failed emails compared to the total emails.

        The method checks the current state of sent and failed emails and updates the
        operation's completion status and result accordingly, ensuring the database
        record reflects the operation's actual progress and outcomes.
        """
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

    def clean(self):
        if self.language and self.language not in self.emailmerge.get_available_languages():
            raise ValidationError(f"EmailMerge is not filled for {self.language} language.")

        super().clean()

    def create(self):
        """
        Creates and queues a batch of emails for sending based on the current
        newsletter configuration. Updates the status of the newsletter and
        saves changes to the database. Constructs an email with specified
        parameters and uses the mail module to send the emails to all recipients.
        The total number of emails sent is stored for record keeping.

        Returns:
            list: A list of EmailModel objects representing the emails that were queued for sending.
        """
        self.status = STATUS.creation
        self.save()
        kwargs = {
            'recipients': list(self.to_recipients.recipients.all()),
            'sender': self.email_from,
            'priority': self.priority,
            'emailmerge': self.emailmerge,
            'context': self.context,
            'language': self.language,
            'scheduled_time': self.scheduled_time,
            'expires_at': self.expires_at,
            'headers': dict(self.headers or {}),
            'newsletter': self,
        }
        emails = mail.send_many(**kwargs)

        self.total_emails = len(emails)
        self.status = STATUS.queued
        self.save()

        return emails


    def save(self, *args, **kwargs):

        if not self.context:
            # If no context, create and save a default schema
            self.context = self.emailmerge.construct_default_json()

        super().save(*args, **kwargs)

    def reparse_context(self):
        self.context = self.emailmerge.construct_default_json()
        self.save()

    class Meta:
        app_label = 'sendmail'
        verbose_name = _('Newsletter')
        verbose_name_plural = _('Newsletters')
