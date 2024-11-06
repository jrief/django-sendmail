from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings

from sendmail.logutils import setup_loghandlers
from sendmail.validators import validate_email_with_name
from .base import AbstractEmailAddress
from ..settings import get_email_address_model

logger = setup_loghandlers('INFO')


class EmailAddress(AbstractEmailAddress):
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
    address = models.ForeignKey(settings.EMAIL_ADDRESS_MODEL, on_delete=models.CASCADE)
    send_type = models.CharField(max_length=12, choices=SEND_TYPES, default='to')

    def __str__(self):
        return self.address.email

    class Meta:
        app_label = 'sendmail'
