from django.db import models
from django.utils.translation import gettext_lazy as _

from sendmail.models.emailaddress import Recipient
from sendmail.settings import get_email_address_setting
from sendmail.models.emailmerge import EmailMergeModel


class RecipientsList(models.Model):
    name = models.CharField(_("List Name"),
                            max_length=255,
                            unique=True)

    recipients = models.ManyToManyField(get_email_address_setting(),
                                        verbose_name=_("Recipients"),
                                        blank=False,
                                        related_name="recipients_list"
                                        )

    class Meta:
        app_label = 'sendmail'
        ordering = ['name']
        verbose_name = _("Recipients List")
        verbose_name_plural = _("Recipients Lists")
