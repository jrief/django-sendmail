from django.db import models
from django.utils.translation import gettext_lazy as _

from sendmail.logutils import setup_loghandlers
from sendmail.models.emailmodel import STATUS, EmailModel

logger = setup_loghandlers('INFO')


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
