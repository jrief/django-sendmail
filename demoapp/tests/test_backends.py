import os
from datetime import timedelta
from email.mime.image import MIMEImage
import pathlib
import pytest

from django.core.files.images import File
from django.core.mail import EmailMultiAlternatives, send_mail, EmailMessage

from sendmail.models import EmailModel, STATUS, PRIORITY


@pytest.mark.django_db
def test_django_email_backend():
    """
    Ensure that Django's email backend does not queue email messages.
    """
    send_mail('Test', 'Message', 'from@example.com', ['to@example.com'])
    assert EmailModel.objects.count() == 0


@pytest.mark.django_db
def test_postoffice_email_backend(settings):
    """
    Ensure that email backend properly queue email messages.
    """
    settings.EMAIL_BACKEND = 'sendmail.EmailBackend'
    send_mail('Test', 'Message', 'from@example.com', ['to@example.com'])
    email = EmailModel.objects.latest('id')
    assert email.subject == 'Test'
    assert email.status == STATUS.queued
    assert email.priority == PRIORITY.medium


# def test_default_settings():
#     """
#     Test for specific post-office settings.
#     """
#     from post_office.config import settings
#
#     assert isinstance(settings.POST_OFFICE, dict)
#     assert settings.POST_OFFICE['BATCH_SIZE'] == 20
#     assert settings.POST_OFFICE['CELERY_ENABLED'] == True
#     assert settings.POST_OFFICE['DEFAULT_PRIORITY'] == 'medium'
#     assert settings.POST_OFFICE['RETRY_INTERVAL'] == timedelta(minutes=15)


@pytest.mark.django_db
def test_send_html_email(settings):
    """
    "text/html" attachments to Email should be persisted into the database
    """
    settings.EMAIL_BACKEND = 'sendmail.EmailBackend'
    message = EmailMultiAlternatives('subject', 'body', 'from@example.com',
                                     ['recipient@example.com'])
    message.attach_alternative('html', "text/html")
    message.send()
    email = EmailModel.objects.latest('id')
    assert email.html_message == 'html'


@pytest.mark.django_db
def test_headers_sent(settings):
    """
    Test that headers are correctly set on the outgoing emails.
    """
    settings.EMAIL_BACKEND = 'sendmail.EmailBackend'
    message = EmailMessage('subject', 'body', 'from@example.com',
                           ['recipient@example.com'],
                           headers={'Mailing-list': 'django-developers@googlegroups.com'})
    message.send()
    email = EmailModel.objects.latest('id')
    assert email.headers == {'Mailing-list': 'django-developers@googlegroups.com'}


@pytest.mark.django_db
def test_reply_to_added_as_header(settings):
    """
    Test that 'Reply-To' headers are correctly set on the outgoing emails,
    when EmailMessage property reply_to is set.
    """
    settings.EMAIL_BACKEND = 'sendmail.EmailBackend'
    message = EmailMessage('subject', 'body', 'from@example.com',
                           ['recipient@example.com'],
                           reply_to=['replyto@example.com', ], )
    message.send()
    email = EmailModel.objects.latest('id')
    assert email.headers == {'Reply-To': 'replyto@example.com'}


@pytest.mark.django_db
def test_reply_to_favors_explict_header(settings):
    """
    Test that 'Reply-To' headers are correctly set, when reply_to property of
    the message object is set and "Reply-To" is also set explictly as a header.
    Then the explicit header value is favored over the message property reply_to,
    adopting the behaviour of message() in django.core.mail.message.EmailMessage.
    """
    settings.EMAIL_BACKEND = 'sendmail.EmailBackend'
    message = EmailMessage('subject', 'body', 'from@example.com',
                           ['recipient@example.com'],
                           reply_to=['replyto-from-property@example.com'],
                           headers={'Reply-To': 'replyto-from-header@example.com'})
    message.send()
    email = EmailModel.objects.latest('id')
    assert email.headers == {'Reply-To': 'replyto-from-header@example.com'}


@pytest.mark.django_db
def test_backend_attachments(settings):
    settings.EMAIL_BACKEND = 'sendmail.EmailBackend'
    message = EmailMessage('subject', 'body', 'from@example.com',
                           ['recipient@example.com'])
    message.attach('attachment.txt', b'attachment content')
    message.send()

    email = EmailModel.objects.latest('id')
    assert email.attachments.count() == 1
    assert email.attachments.all()[0].name == 'attachment.txt'
    assert email.attachments.all()[0].file.read() == b'attachment content'


@pytest.mark.django_db
def test_backend_image_attachments(settings):
    settings.EMAIL_BACKEND = 'sendmail.EmailBackend'
    message = EmailMessage('subject', 'body', 'from@example.com',
                           ['recipient@example.com'])

    filename = pathlib.Path(__file__).parent / 'assets/logo.png'
    with open(filename, 'rb') as fh:
        fileobj = File(fh, name='dummy.png')
        image = MIMEImage(fileobj.read())
    image.add_header('Content-Disposition', 'inline', filename='dummy.png')
    image.add_header('Content-ID', '<{dummy.png}>')
    message.attach(image)
    message.send()

    email = EmailModel.objects.latest('id')
    assert email.attachments.count() == 1
    assert email.attachments.all()[0].name == 'dummy.png'
    assert email.attachments.all()[0].file.read() == image.get_payload().encode()
    assert email.attachments.all()[0].headers.get('Content-ID') == '<{dummy.png}>'
    assert email.attachments.all()[0].headers.get('Content-Disposition') == 'inline; filename="dummy.png"'


@pytest.mark.django_db
def test_default_priority_now(settings):
    settings.EMAIL_BACKEND = 'sendmail.EmailBackend'
    settings.SENDMAIL = {
        'DEFAULT_PRIORITY': 'now',
        'BACKENDS': {'default': 'django.core.mail.backends.dummy.EmailBackend'},
    }

    # If DEFAULT_PRIORITY is "now", mails should be sent right away
    num_sent = send_mail('Test', 'Message', 'from1@example.com', ['to@example.com'])
    email = EmailModel.objects.latest('id')
    assert email.status == STATUS.sent
    assert num_sent == 1


@pytest.mark.django_db
def test_email_queued_signal(settings, mocker):
    settings.EMAIL_BACKEND = 'sendmail.EmailBackend'
    settings.SENDMAIL = {
        'DEFAULT_PRIORITY': 'medium',
        'BACKENDS': {'default': 'django.core.mail.backends.dummy.EmailBackend'},
    }
    magic_mock = mocker.patch('sendmail.signals.email_queued.send')
    # If DEFAULT_PRIORITY is not "now", the email_queued signal should be sent
    send_mail('Test', 'Message', 'from1@example.com', ['to@example.com'])
    email = EmailModel.objects.latest('id')
    assert email.status == STATUS.queued
    magic_mock.assert_called_once()
