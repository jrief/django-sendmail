import logging
import tempfile
from datetime import datetime
from django.core.files import File
from django.core.files.base import ContentFile
import pytest
from sendmail.utils import set_recipients, get_recipients_objects, parse_emails, parse_priority, split_emails, \
    create_attachments, send_mail, get_email_template, cleanup_expired_mails, get_language_from_code
from sendmail.models import EmailAddress, EmailModel, PRIORITY, Attachment, STATUS, EmailMergeModel
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage, FileSystemStorage

from sendmail.settings import get_attachments_storage

from sendmail.validators import validate_email_with_name, validate_template_syntax


@pytest.mark.django_db
def test_set_recipients():
    # Create test email
    test_email = EmailModel.objects.create(from_email='test@email.com', language='en')

    # Create test addresses
    to_recipients = [EmailAddress.objects.create(email=f"{i}@email.com") for i in range(5)]
    cc_recipients = [EmailAddress.objects.create(email=f"{i}@gmail.com") for i in range(5)]
    bcc_recipients = [EmailAddress.objects.create(email=f"{6 + i}@yahoo.com") for i in range(5)]

    # Test 'to' addresses
    set_recipients(test_email, to_addresses=to_recipients)

    assert test_email.recipients.count() == 5

    # Test 'cc' and 'bcc' addresses
    set_recipients(test_email, [], cc_addresses=cc_recipients, bcc_addresses=bcc_recipients)

    assert test_email.recipients.count() == 15

    # Validate recipients
    recipient_objs = test_email.recipients.through.objects.all()

    assert len(recipient_objs) == 15

    # Check 'to' recipients
    to_recipient_emails = [rec.address.email for rec in recipient_objs.filter(send_type='to')]
    assert sorted(to_recipient_emails) == sorted(addr.email for addr in to_recipients)

    # Check 'cc' recipients
    cc_recipient_emails = [rec.address.email for rec in recipient_objs.filter(send_type='cc')]
    assert sorted(cc_recipient_emails) == sorted(addr.email for addr in cc_recipients)

    # Check 'bcc' recipients
    bcc_recipient_emails = [rec.address.email for rec in recipient_objs.filter(send_type='bcc')]
    assert sorted(bcc_recipient_emails) == sorted(addr.email for addr in bcc_recipients)


@pytest.mark.django_db
def test_get_recipients(caplog):
    test_recipient = EmailAddress.objects.create(email='test1@email.com',
                                                 first_name='John',
                                                 last_name='Doe',
                                                 is_blocked=False)
    assert (recipient_list := get_recipients_objects(['test1@email.com'])) == [test_recipient]

    assert get_recipients_objects([test_recipient]) == [test_recipient]

    assert recipient_list[0].first_name, recipient_list[0].last_name == ('John', 'Doe')

    with caplog.at_level(logging.WARNING):
        new_recipients = get_recipients_objects(['test1@email.com', 'test2@email.com'])
        assert "is blocked" not in caplog.text

    created_recipient = EmailAddress.objects.get(email='test2@email.com')

    unsaved_recipient = EmailAddress(first_name='Alice', last_name='Green', email='alisa@green')
    assert get_recipients_objects([test_recipient, unsaved_recipient]) == [test_recipient, unsaved_recipient]
    EmailAddress.objects.get(email='alisa@green')
    unsaved_recipient.is_blocked = True
    unsaved_recipient.save()
    with caplog.at_level(logging.WARNING):
        get_recipients_objects([test_recipient, unsaved_recipient])
        assert "User alisa@green is blocked and hence will be excluded" in caplog.text

    assert not created_recipient.is_blocked

    assert len(new_recipients) == 2
    assert new_recipients[1] == created_recipient

    test_recipient.is_blocked = True
    test_recipient.save()

    with caplog.at_level(logging.WARNING):
        recs = get_recipients_objects(['test1@email.com', 'test2@email.com'])
        assert "User test1@email.com is blocked and hence will be excluded" in caplog.text

    assert not created_recipient.is_blocked

    assert len(recs) == 1
    assert recs[0] == created_recipient


def test_parse_emails():
    assert parse_emails('test@exmaple.com') == ['test@exmaple.com']

    assert not parse_emails(None)

    with pytest.raises(ValidationError):
        parse_emails('invalid_email')

    with pytest.raises(ValidationError):
        parse_emails(['invalida_email', 'test@exmaple.com'])


def test_parse_priority(settings):
    settings.SENDMAIL['DEFAULT_PRIORITY'] = 'low'
    assert parse_priority('now') == PRIORITY.now
    assert parse_priority('high') == PRIORITY.high
    assert parse_priority('medium') == PRIORITY.medium
    assert parse_priority('low') == PRIORITY.low

    with pytest.raises(ValueError):
        assert parse_priority('not_valid')

    assert parse_priority(None) == PRIORITY.low


@pytest.mark.django_db
def test_split_emails():
    for _ in range(225):
        EmailModel.objects.create(from_email='test@email.com', language='en')
    expected_size = [57, 56, 56, 56]
    email_list = split_emails(EmailModel.objects.all(), 4)
    assert expected_size == [len(emails) for emails in email_list]

    assert split_emails([]) == []


@pytest.fixture
def test_template():
    template = EmailMergeModel.objects.create(
        base_file='test/test.html',
        name='test_name',
        description='test_description',
        # subject='test_subject',
        # content='test_content',
        # language='en',
    )

    en_content = template.translated_contents.get(language='en')
    en_content.subject = 'test_subject'
    en_content.content = 'test_content'
    en_content.save()
    return template


@pytest.mark.django_db
def test_get_template(settings, test_template):
    assert get_email_template('test_name') == test_template
    settings.POST_OFFICE_TEMPLATE_CACHE = False
    assert get_email_template('test_name') == test_template


@pytest.mark.django_db
def test_create_attachment():
    attachments = create_attachments(
        {
            'attachment_file1.txt': ContentFile('content'),
            'attachment_file2.txt': ContentFile('content'),
        }
    )

    assert len(attachments) == 2
    assert isinstance(attachments[0], Attachment)
    assert attachments[0].pk
    assert attachments[0].file.read() == b'content'
    assert attachments[0].name.startswith('attachment_file')
    assert attachments[0].mimetype == ''


@pytest.mark.django_db
def test_create_attachment_with_mimetype():
    attachments = create_attachments(
        {
            'attachment_file1.txt': {'file': ContentFile('content'), 'mimetype': 'text/plain'},
            'attachment_file2.jpg': {'file': ContentFile('content'), 'mimetype': 'text/plain'},
        }
    )

    assert len(attachments) == 2
    assert isinstance(attachments[0], Attachment)
    assert attachments[0].pk
    assert attachments[0].file.read() == b'content'
    assert attachments[0].name.startswith('attachment_file')
    assert attachments[0].mimetype == 'text/plain'


@pytest.mark.django_db
def test_create_attachments_open_file():
    attachments = create_attachments({'attachment_file.py': __file__})

    assert len(attachments) == 1
    assert isinstance(attachments[0], Attachment)
    assert attachments[0].pk
    assert attachments[0].file.read()
    assert attachments[0].name == 'attachment_file.py'
    assert attachments[0].mimetype == ''


@pytest.mark.django_db
def test_email_validator():
    validate_email_with_name('email@example.com')
    validate_email_with_name('Alice Bob <email@example.com>')
    EmailModel.objects.create(
        from_email='Alice <from@example.com>',
        subject='Test',
        message='Message',
        status=STATUS.sent,
        language='en'
    )

    # Should also support international domains
    validate_email_with_name('Alice Bob <email@example.co.id>')

    with pytest.raises(ValidationError):
        validate_email_with_name('invalid')

    with pytest.raises(ValidationError):
        validate_email_with_name('Al <ab>')

    with pytest.raises(ValidationError):
        validate_email_with_name('Al <>')


@pytest.mark.django_db
def test_send_email():
    send_mail('subject', 'message', 'from@example.com', ['to@example.com'], priority=PRIORITY.medium)
    email = EmailModel.objects.latest('id')
    assert email.status == STATUS.queued

    # Emails sent with "now" priority is sent right away
    send_mail('subject', 'message', 'from@example.com', ['to@example.com'], priority=PRIORITY.now)
    email = EmailModel.objects.latest('id')
    assert email.status == STATUS.sent


@pytest.mark.django_db
def test_cleanup_expired():
    assert cleanup_expired_mails(datetime.now()) == (0, 0)
    email = EmailModel.objects.create(from_email='test@email.com', language='en')
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(b'Test attachment')
        tmp.seek(0)
        file = File(tmp)
        attachment = Attachment.objects.create(file=file,
                                               name='attach')
        email.attachments.set([attachment])
    assert cleanup_expired_mails(datetime.now(), delete_attachments=False) == (1, 0)

    assert EmailModel.objects.count() == 0

    assert Attachment.objects.count() == 1

    assert cleanup_expired_mails(datetime.now(), delete_attachments=True) == (0, 1)

    assert Attachment.objects.count() == 0


def test_template_syntax():
    validate_template_syntax("<h1>{{ test.value }}"
                             "{% for template in test.values %}"
                             "{{ template }}"
                             "{% endfor %}"
                             "</h1>")

    with pytest.raises(ValidationError):
        validate_template_syntax("{% invalid %}")

    with pytest.raises(ValidationError):
        validate_template_syntax("<h1>{{ test.value }}"
                                 "{% for template in test.values %}"
                                 "{{ template }}"
                                 "</h1>")


def test_get_language_from_code():
    assert get_language_from_code('en') == 'en'
    assert get_language_from_code(None) == 'en'
    assert get_language_from_code('de') == 'de'
    assert get_language_from_code('fr') == 'en'


def test_default_storage(settings):
    assert get_attachments_storage() == default_storage

    settings.STORAGES.update({'sendmail_attachments': {'sendmail_attachments': {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {
            "location": settings.MEDIA_ROOT,  # Specify the directory for storage
        }
    }}})

    assert isinstance(storage := get_attachments_storage(), FileSystemStorage)

    assert storage.base_url == '/media/'
