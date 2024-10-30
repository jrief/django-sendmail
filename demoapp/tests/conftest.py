import time

import pytest
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.mail.backends.base import BaseEmailBackend
from django.conf import settings


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


@pytest.fixture(scope='session', autouse=True)
def upload_images():
    source_dir = settings.BASE_DIR / 'demoapp/tests/assets'
    uploaded_files = []

    for filename in source_dir.glob("*"):
        with filename.open('rb') as f:
            django_file = File(f)
            filepath = default_storage.save(str(filename.name), django_file)
            uploaded_files.append(filepath)

    yield uploaded_files

    for filepath in uploaded_files:
        if default_storage.exists(filepath):
            default_storage.delete(filepath)
