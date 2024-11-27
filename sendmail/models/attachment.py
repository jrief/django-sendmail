import os
from uuid import uuid4

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from sendmail.logutils import setup_loghandlers
from sendmail.models.emailmodel import EmailModel
from sendmail.settings import get_attachments_storage

logger = setup_loghandlers('INFO')


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
    emails = models.ManyToManyField(EmailModel,
                                    related_name='attachments',
                                    verbose_name=_('Emails'),
                                    blank=True,
                                    editable=False)

    mimetype = models.CharField(max_length=255, default='', blank=True)
    headers = models.JSONField(_('Headers'), blank=True, null=True)

    class Meta:
        app_label = 'sendmail'
        verbose_name = _('Attachment')
        verbose_name_plural = _('Attachments')

    def __str__(self):
        return self.name
