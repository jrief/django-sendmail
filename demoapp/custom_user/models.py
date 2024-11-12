from django.db import models

from sendmail.mixins import SwappableMetaMixin
from sendmail.models.base import AbstractEmailAddress


class CustomEmailAddress(AbstractEmailAddress, SwappableMetaMixin):
    phone_number = models.CharField(max_length=20, blank=True, null=True)
