from sendmail.models.base import AbstractEmailAddress
from django.db import models


class CustomEmailAddress(AbstractEmailAddress):
    phone_number = models.CharField(max_length=20, blank=True, null=True)

    class Meta:
        pass
