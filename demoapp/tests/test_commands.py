import timeit
from unittest import mock

import pytest
import datetime
import os

from django.core.files.base import ContentFile
from django.core.management import call_command
from django.utils.timezone import now

from sendmail.mail import send
from sendmail.models import EmailModel, Attachment, STATUS, EmailAddress
from sendmail.utils import set_recipients


@pytest.mark.django_db
def test_cleanup_mail_with_orphaned_attachments():
    assert EmailModel.objects.count() == 0
    email = EmailModel.objects.create(from_email='from@example.com', subject='Subject', language='en')

    email.created = now() - datetime.timedelta(31)
    email.save()

    attachment = Attachment()
    attachment.file.save('test.txt', content=ContentFile('test file content'), save=True)
    email.attachments.add(attachment)
    attachment_path = attachment.file.name

    call_command('cleanup_mail', days=30)
    assert EmailModel.objects.count() == 0
    assert Attachment.objects.count() == 1

    call_command('cleanup_mail', '-da', days=30)
    assert EmailModel.objects.count() == 0
    assert Attachment.objects.count() == 0

    assert not os.path.exists(attachment_path)

    EmailModel.objects.all().delete()
    email = EmailModel.objects.create(from_email='from@example.com', subject='Subject', language='en')
    email.created = now() - datetime.timedelta(31)
    email.save()

    attachment = Attachment()
    attachment.file.save('test.txt', content=ContentFile('test file content'), save=True)
    email.attachments.add(attachment)
    attachment_path = attachment.file.path

    # Simulate that the files have been deleted by accidents
    os.remove(attachment_path)

    call_command('cleanup_mail', '-da', days=30)
    assert EmailModel.objects.count() == 0
    assert Attachment.objects.count() == 0


@pytest.mark.django_db
def test_cleanup_mail():
    """
    The ``cleanup_mail`` command deletes mails older than a specified
    amount of days
    """
    assert EmailModel.objects.count() == 0

    # The command shouldn't delete today's email
    email = EmailModel.objects.create(from_email='from@example.com', language='en')
    call_command('cleanup_mail', days=30)
    assert EmailModel.objects.count() == 1

    # Email older than 30 days should be deleted
    email.created = now() - datetime.timedelta(days=31)
    email.save()
    call_command('cleanup_mail', days=30)
    assert EmailModel.objects.count() == 0


@pytest.mark.django_db
def test_send_queued_mail():
    with mock.patch('django.db.connection.close', return_value=None):
        call_command('send_queued_mail', processes=1)

        EmailModel.objects.create(from_email='from@example.com', status=STATUS.queued, language='en')
        EmailModel.objects.create(from_email='from@example.com', status=STATUS.queued, language='en')
        call_command('send_queued_mail', processes=1)
        assert EmailModel.objects.filter(status=STATUS.sent).count() == 2
        assert EmailModel.objects.filter(status=STATUS.queued).count() == 0


@pytest.mark.django_db
def test_successful_deliveries_log():
    with mock.patch('django.db.connection.close', return_value=None):
        email = EmailModel.objects.create(from_email='from@example.com', status=STATUS.queued, language='en')
        call_command('send_queued_mail', log_level=0)
        assert email.logs.count() == 0

        email = EmailModel.objects.create(from_email='from@example.com', status=STATUS.queued, language='en')
        call_command('send_queued_mail', log_level=1)
        assert email.logs.count() == 0

        email = EmailModel.objects.create(from_email='from@example.com', status=STATUS.queued, language='en')
        call_command('send_queued_mail', log_level=2)
        assert email.logs.count() == 1


@pytest.mark.django_db
def test_failed_deliveries_logging():
    """
    Failed deliveries are logged when log_level is 1 and 2.
    """

    with mock.patch('django.db.connection.close', return_value=None):
        recipient = EmailAddress.objects.create(email=f'to@example.com')
        email = EmailModel.objects.create(
            from_email='from@example.com', status=STATUS.queued, backend_alias='error', language='en'
        )
        set_recipients(email, [recipient])

        call_command('send_queued_mail', log_level=0)
        assert email.logs.count() == 0

        email = EmailModel.objects.create(
            from_email='from@example.com', status=STATUS.queued, backend_alias='error', language='en'
        )
        set_recipients(email, [recipient])

        call_command('send_queued_mail', log_level=1)
        assert email.logs.count() == 1

        email = EmailModel.objects.create(
            from_email='from@example.com', status=STATUS.queued, backend_alias='error', language='en'
        )
        set_recipients(email, [recipient])
        call_command('send_queued_mail', log_level=2)
        assert email.logs.count() == 1


# @pytest.mark.django_db
# def test_multiprocessing(settings):
#     def slowly_send_2_emails(processes):
#         recipient = EmailAddress.objects.create(email=f'to{processes}@example.com')
#         email1 = EmailModel.objects.create(
#             from_email='from@example.com', status=STATUS.queued, backend_alias='slow_backend'
#         )
#         set_recipients(email1, [recipient])
#         email2 = EmailModel.objects.create(
#             from_email='from@example.com', status=STATUS.queued, backend_alias='slow_backend'
#         )
#
#         set_recipients(email2, [recipient])
#
#         call_command('send_queued_mail', processes=processes, prevent_db_close=True)
#
#     execution_time = timeit.timeit(lambda: slowly_send_2_emails(1), number=1)
#     assert execution_time > 10 <= 11
#
#     execution_time = timeit.timeit(lambda: slowly_send_2_emails(2), number=1)
#     assert execution_time > 5 <= 6
