import time

from django.core.mail.backends.base import BaseEmailBackend


class ErrorRaisingBackend(BaseEmailBackend):
    """
    An EmailBackend that always raises an error during sending
    to test if django_mailer handles sending error correctly
    """

    def send_messages(self, email_messages):
        raise Exception('Fake Error')


class SlowTestBackend(BaseEmailBackend):
    """
    An EmailBackend that sleeps for 10 seconds when sending messages
    """

    def send_messages(self, email_messages):
        time.sleep(5)
