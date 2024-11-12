import os
import time

import pytest
from django.conf import settings
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.mail.backends.base import BaseEmailBackend
from sendmail.models.emailmerge import EmailMergeModel

from .mailpit import MailpitConnector

os.environ.setdefault('DJANGO_ALLOW_ASYNC_UNSAFE', 'true')


@pytest.fixture
def locale():
    return 'en-US'


@pytest.fixture
def language():
    return 'en'


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


@pytest.fixture(scope='session')
def email_testing():
    with MailpitConnector() as mailpit:
        yield mailpit


@pytest.fixture
def template():
    template_context = EmailMergeModel.objects.create(
        template_file='test/context_test.html',
        name='test_template',
        description='test_description',
    )

    en_translation = template_context.translated_contents.create(language='en')
    en_translation.subject = 'template_subject'
    en_translation.content = 'template_content'
    en_translation.save()

    de_translation = template_context.translated_contents.create(language='de')
    de_translation.subject = 'DE test_subject'
    de_translation.content = 'DE test_content'

    de_translation.save()

    return template_context
