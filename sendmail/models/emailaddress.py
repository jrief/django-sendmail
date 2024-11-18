from django.db import models
from django.utils.translation import gettext_lazy as _

from sendmail.logutils import setup_loghandlers
from sendmail.models.base import AbstractEmailAddress
from sendmail.settings import get_email_address_setting

logger = setup_loghandlers('INFO')


class EmailAddress(AbstractEmailAddress):
    """
    Default implementation of EmailAddress model. Used by default if EMAIL_ADDRESS_MODEL is not provided.
    """

    class Meta:
        app_label = 'sendmail'


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
    address = models.ForeignKey(get_email_address_setting(), on_delete=models.CASCADE)
    send_type = models.CharField(max_length=12, choices=SEND_TYPES, default='to')

    def __str__(self):
        return self.address.email

    class Meta:
        app_label = 'sendmail'
