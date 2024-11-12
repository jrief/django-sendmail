from django.db import models
from django.utils.translation import gettext_lazy as _

from sendmail.validators import validate_email_with_name


class AbstractEmailAddress(models.Model):
    """
    Abstract model to hold email recipient information.
    """
    GENDERS = [
        ('male', _('Male')),
        ('female', _('Female')),
        ('other', _('Other')),
    ]
    email = models.CharField(_('Email'),
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
        abstract = True
