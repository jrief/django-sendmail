import logging
from datetime import timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from sendmail.mail import create, send, send_many, split_into_batches, get_queued, _send_bulk
from sendmail.models import PRIORITY, EmailModel, EmailAddress, EmailMergeModel, PlaceholderContent, STATUS, \
    Attachment, Recipient
from django.core.exceptions import ValidationError
import tempfile
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.utils import timezone
from django.db.utils import InterfaceError

from sendmail.settings import get_available_backends


#from django.conf import settings


@pytest.fixture
def template():
    template_context = EmailMergeModel.objects.create(
        base_file='test/context_test.html',
        name='test_template',
        description='test_description',
    )

    en_translation = template_context.translated_contents.get(language='en')
    en_translation.subject = 'template_subject'
    en_translation.content = 'template_content'
    en_translation.save()

    de_translation = template_context.translated_contents.get(language='de')
    de_translation.subject = 'DE test_subject'
    de_translation.content = 'DE test_content'

    de_translation.save()

    return template_context


@pytest.fixture
def recipient():
    return EmailAddress.objects.create(email='john@gmail.com',
                                       first_name='John',
                                       last_name='Doe',
                                       gender='male',
                                       preferred_language='en')


@pytest.mark.django_db
def test_create_email(template):
    recipients = ['rec1@gmail.com', 'rec2@gmail.com']
    sender = 'sender@gmail.com'

    email_model = create(sender=sender,
                         recipients=recipients,
                         subject='subject',
                         message='message',
                         html_message='html_message',
                         priority='medium',
                         commit=True,
                         language='en', )

    assert EmailModel.objects.count() == 1
    email = EmailModel.objects.first()
    assert email.id == email_model.id
    assert email.from_email == sender
    assert email.subject == 'subject'
    assert email.message == 'message'
    assert email.html_message == 'html_message'
    assert email.priority == PRIORITY.medium
    assert (recipient_id := email.context['recipient'])
    assert email.status == STATUS.queued
    assert EmailAddress.objects.count() == 2

    assert EmailAddress.objects.get(pk=recipient_id).email == recipients[0]

    create(sender=sender,
           recipients=recipients,
           subject='subject',
           message='message',
           html_message='html_message',
           priority='medium',
           commit=False,
           language='en')

    assert EmailModel.objects.count() == 1

    email_model = create(sender=sender,
                         recipients=recipients,
                         template=template,
                         priority='medium',
                         commit=True,
                         language='en')

    assert EmailModel.objects.count() == 2
    email = EmailModel.objects.last()
    assert email.id == email_model.id
    assert email.subject == 'template_subject'
    assert email.message == 'template_content'

    new_recipient = EmailAddress.objects.create(email='john@gmail.com',
                                                first_name='John',
                                                last_name='Doe',
                                                gender='male',
                                                preferred_language='en')

    context = {'recipient': new_recipient}
    email_model = create(sender=sender,
                         recipients=recipients,
                         template=template,
                         priority='medium',
                         commit=True,
                         context=context,
                         language='en')

    assert email_model.context['recipient'] == new_recipient.id

    cc = ['cc1@gmail.com', 'cc2@gmail.com']
    bcc = ['bcc1@gmail.com', 'bcc2@gmail.com']
    email_model = create(sender=sender,
                         cc=cc,
                         bcc=bcc,
                         template=template,
                         priority='medium',
                         commit=True,
                         context=context,
                         language='en')
    em = EmailModel.objects.get(pk=email_model.id)
    assert em.recipients.count() == 4
    assert list(em.recipients.values_list('email', flat=True)).sort() == [*cc, *bcc].sort()


@pytest.mark.django_db
def test_send_email(template, recipient):
    recipients = ['rec1@gmail.com', 'rec2@gmail.com']
    cc = ['cc1@gmail.com', 'cc2@gmail.com']
    bcc = ['bcc1@gmail.com', 'bcc2@gmail.com']
    sender = 'sender@gmail.com'
    context = {'recipient': recipient}
    email_model = send(sender=sender,
                       recipients=recipients,
                       template=template,
                       priority='medium',
                       commit=True,
                       context=context,
                       cc=cc,
                       bcc=bcc)
    assert email_model.language == 'en'

    email = send(sender=sender,
                 recipients=recipients,
                 template=template,
                 priority='medium',
                 commit=True,
                 context=context,
                 language='es')

    assert email.language == 'en'

    with pytest.raises(ValidationError):
        nv_recipients = [*recipients, 'not_valid']
        send(sender=sender,
             recipients=nv_recipients,
             template=template,
             priority='medium',
             commit=True,
             context=context,
             language='en')

    with pytest.raises(ValidationError):
        nv_cc = [*cc, 'not_valid']
        send(sender=sender,
             recipients=recipients,
             template=template,
             priority='medium',
             commit=True,
             context=context,
             language='en',
             cc=nv_cc)

    with pytest.raises(ValidationError):
        nv_bcc = [*bcc, 'not_valid']
        send(sender=sender,
             recipients=recipients,
             template=template,
             priority='medium',
             commit=True,
             context=context,
             language='en',
             cc=cc,
             bcc=nv_bcc)

    mail = send(
        recipients=recipients,
        template=template,
        priority='medium',
        commit=True,
        context=context,
        language='en',
        cc=cc)

    assert mail.from_email == 'default@email.com'

    with pytest.raises(ValueError):
        send(
            recipients=recipients,
            template=template,
            priority='now',
            commit=False,
            context=context,
            language='en',
            cc=cc)

    with pytest.raises(ValueError):
        send(recipients=recipients,
             template=template,
             subject='subject',
             priority='medium',
             commit=True,
             context=context,
             language='en', )

    with pytest.raises(ValueError):
        send(recipients=recipients,
             template=template,
             message='message',
             priority='medium',
             commit=True,
             context=context,
             language='en', )

    with pytest.raises(ValueError):
        send(recipients=recipients,
             template=template,
             html_message='<h1>Hi</hi>',
             priority='medium',
             commit=True,
             context=context,
             language='en', )

    mail = send(
        recipients=recipients,
        template='test_template',
        priority='medium',
        commit=True,
        context=context,
        language='en',
    )

    assert mail.template == template

    assert EmailModel.objects.last().template == EmailMergeModel.objects.get(name='test_template')

    mail = send(
        recipients=recipients,
        template=template,
        priority='medium',
        commit=True,
        context=context,
        language='de',
    )

    assert mail.template == EmailMergeModel.objects.get(name='test_template')

    mail = send(
        recipients=recipients,
        template='test_template',
        priority='medium',
        commit=True,
        context=context,
        language='de',
    )

    assert mail.template == EmailMergeModel.objects.get(name='test_template')

    with pytest.raises(ValueError):
        send(
            recipients=recipients,
            template='test_template',
            priority='medium',
            commit=True,
            context=context,
            language='de',
            backend='nv_backend'
        )

    mail = send(
        recipients=recipients,
        template='test_template',
        priority='medium',
        commit=True,
        context=context,
        language='de',
        backend='default'
    )

    assert mail.backend_alias == 'default'

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(b'Testing payload')
        tmp.seek(0)
        mail = send(
            recipients=recipients,
            template='test_template',
            priority='medium',
            commit=True,
            context=context,
            language='de',
            backend='default',
            attachments={'test.txt': tmp}
        )
    assert Attachment.objects.count() == 1
    attachment = Attachment.objects.first()
    assert list(mail.attachments.all()) == [attachment]

    mail = send(
        recipients=recipients,
        template='test_template',
        priority='now',
        commit=True,
        context=context,
        language='de',
        backend='default',
    )

    assert mail.status == STATUS.sent


@pytest.mark.django_db
def test_send_many(template):
    recipients = ['mrec1@gmail.com', 'mrec2@gmail.com']
    sender = 'from@gmail.com'
    with pytest.raises(ValueError):
        send_many(sender=sender, template=template)

    with pytest.raises(ValidationError):
        send_many(sender=sender, recipients=['nv', 'valid@email.com'], template=template)

    with CaptureQueriesContext(connection) as ctx:
        emails = send_many(
            sender=sender,
            template=template,
            recipients=recipients,
            context={'test': 'val'}
        )
        insert_queries = [query for query in ctx.captured_queries if query['sql'].strip().lower().startswith('insert')]

        # 1. Create EmailAddress in bulk_create
        # 2. Create Recipients in bulk_create
        # 3. Create EmailModels in bulk_create
        assert len(insert_queries) == 3

    with pytest.raises(ValueError):
        emails = send_many(
            sender=sender,
            template=template,
            recipients=recipients,
            context={'test': 'val'},
            cc=['test@gmail.com']
        )

    assert len(emails) == 2
    assert EmailModel.objects.count() == 2

    mrec1 = EmailAddress.objects.get(email='mrec1@gmail.com')
    mrec2 = EmailAddress.objects.get(email='mrec2@gmail.com')

    assert list(emails[0].recipients.all()) == [mrec1]
    assert list(emails[1].recipients.all()) == [mrec2]

    rec_objs = Recipient.objects.all()
    assert rec_objs.count() == 2

    assert all([rec.send_type == 'to' for rec in rec_objs])
    assert [rec_objs[0].email, rec_objs[1].email] == emails

    assert emails[0].context == {'test': 'val', 'recipient': mrec1.id}
    assert emails[1].context == {'test': 'val', 'recipient': mrec2.id}

    new_recipients = ['nmrec1@gmail.com', 'nmrec2@gmail.com']

    with CaptureQueriesContext(connection) as ctx:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            with tempfile.NamedTemporaryFile(delete=False) as tmp2:
                tmp.write(b'Testing payload 1')
                tmp.seek(0)
                tmp2.write(b'Testing payload 2')
                tmp2.seek(0)
                emails = send_many(
                    sender=sender,
                    template=template,
                    recipients=new_recipients,
                    context={'test': 'val'},
                    attachments={'test.txt': tmp, 'new.txt': tmp2},
                )
        insert_queries = [query for query in ctx.captured_queries if
                          query['sql'].strip().lower().startswith('insert')]

        # 1. Create EmailAddress in bulk_create
        # 2. Create Recipients in bulk_create
        # 3. Create EmailModels in bulk_create
        # 4-5. Create Attachments (2 times)
        # 6. Create Through objects in bulk_create
        assert len(insert_queries) == 6

    assert emails[0].attachments.count() == 2

    assert list(emails[0].attachments.all()) == list(emails[1].attachments.all())

    assert list(emails[0].attachments.values_list('name', flat=True)) == ['test.txt', 'new.txt']


@pytest.mark.django_db
def test_internalization(caplog, template):
    en_recipient = EmailAddress.objects.create(
        email='en@gmail.com',
        first_name='EN',
        preferred_language='en'
    )

    de_recipient = EmailAddress.objects.create(
        email='de@gmail.com',
        first_name='DE',
        preferred_language='de'
    )

    ua_recipient = EmailAddress.objects.create(
        email='ua@gmail.com',
        first_name='UA',
        preferred_language='ua'
    )

    nullable_recipient = EmailAddress.objects.create(
        email='nullable@gmail.com',
        first_name='NL',
    )

    with caplog.at_level(logging.WARNING):
        emails = send_many(
            recipients=[en_recipient, de_recipient, ua_recipient, nullable_recipient],
            template=template)

        assert 'Language "ua" is not found in LANGUAGES configuration' in caplog.text

    assert len(emails) == 4
    assert emails[0].language == 'en'
    assert emails[1].language == 'de'
    assert emails[2].language == 'en'
    assert emails[3].language == 'en'

    caplog.clear()

    with caplog.at_level(logging.WARNING):
        emails = send_many(
            recipients=[en_recipient, de_recipient, ua_recipient, nullable_recipient],
            template=template,
            language='en')

        assert 'Language "ua" is not found in LANGUAGES configuration.' not in caplog.text

    assert all([email.language == 'en' for email in emails])


def test_split_batches(settings):
    settings.SENDMAIL['BATCH_SIZE'] = 2
    assert split_into_batches([1, 2, 3, 4, 5, 6, 7]) == [[1, 2], [3, 4], [5, 6], [7]]


@pytest.mark.django_db
def test_get_queued():
    kwargs = {
        'from_email': 'bob@example.com',
        'subject': 'Test',
        'message': 'Message',
        'language': 'en'
    }
    assert list(get_queued()) == []

    EmailModel.objects.create(status=STATUS.failed, **kwargs)
    EmailModel.objects.create(status=None, **kwargs)
    EmailModel.objects.create(status=STATUS.sent, **kwargs)
    assert list(get_queued()) == []

    queued_email = EmailModel.objects.create(status=STATUS.queued, scheduled_time=None, **kwargs)
    assert list(get_queued()) == [queued_email]

    scheduled_time = timezone.now() + timedelta(days=1)
    EmailModel.objects.create(status=STATUS.queued, scheduled_time=scheduled_time, **kwargs)
    assert list(get_queued()) == [queued_email]

    past_email = EmailModel.objects.create(
        status=STATUS.queued, scheduled_time=timezone.datetime(2010, 12, 13), **kwargs
    )
    assert list(get_queued()) == [queued_email, past_email]


from django.core import mail


@pytest.mark.django_db
def test_send_bulk(template):
    recipients = ['mrec1@gmail.com', 'mrec2@gmail.com']
    sender = 'from@gmail.com'
    context = {'test': 'val'}
    email = send(
        sender=sender,
        recipients=recipients,
        template=template,
        priority='medium',
        commit=True,
        context=context,
        language='de',
        backend='default',
    )
    _send_bulk([email], uses_multiprocessing=False)
    assert EmailModel.objects.get(id=email.id).status == STATUS.sent


@pytest.mark.django_db
def test_errors(settings, template):
    email_model = send(
        recipients=['test@gmail.com'],
        template=template,
        priority='now',
        commit=True,
        backend='error', )
    assert email_model.status == STATUS.failed

    recipients = ['mrec1@gmail.com', 'mrec2@gmail.com']
    sender = 'from@gmail.com'
    context = {'test': 'val'}
    email = send(
        sender=sender,
        recipients=recipients,
        template=template,
        priority='medium',
        commit=True,
        context=context,
        language='de',
        backend='error',
    )
    settings.SENDMAIL['MAX_RETRIES'] = 1
    assert not email.number_of_retries

    _send_bulk([email], uses_multiprocessing=False)

    assert email.status == STATUS.requeued
    assert email.number_of_retries == 1

    _send_bulk([email], uses_multiprocessing=False)

    assert email.status == STATUS.failed

    with pytest.raises(InterfaceError):
        # Connection already closed
        _send_bulk([email], uses_multiprocessing=True)


@pytest.mark.django_db
def test_extra_recipients(template):
    extra_recipients = [EmailAddress.objects.create(email='bcc1@email.com'),
                        EmailAddress.objects.create(email='bcc2@email.com')]

    template.extra_recipients.set(extra_recipients)

    template.save()

    recipients = ['mrec1@gmail.com', 'mrec2@gmail.com']
    sender = 'from@gmail.com'
    context = {'test': 'val'}
    email = send(
        sender=sender,
        recipients=recipients,
        template=template,
        priority='medium',
        commit=True,
        context=context,
        language='de',
        backend='default',
    )

    assert email.recipients.count() == 4

    assert (recipients := Recipient.objects.all()).count() == 4

    assert (extra := recipients.filter(send_type='bcc')).count() == 2

    assert extra[0].address.email == 'bcc1@email.com'
    assert extra[1].address.email == 'bcc2@email.com'


from django.core.files.base import ContentFile


@pytest.fixture
def template_with_extra_attachments(settings, template):
    en_translation = template.translated_contents.get(language='en')

    en_path = settings.BASE_DIR / 'demoapp' / 'tests' / 'assets' / 'en_attachment.txt'

    with open(en_path, 'rb') as f:
        file = ContentFile(f.read(), name='en_attachment.txt')
        en_attachment = Attachment.objects.create(
            file=file,
            name='en_attachment.txt',
            mimetype='text/plain'
        )
    en_translation.extra_attachments.set([en_attachment])
    en_translation.save()

    return template


@pytest.mark.django_db
def test_extra_attachments(settings, template_with_extra_attachments):
    # Retrieve the template with the extra attachments already set up
    template = template_with_extra_attachments
    en_translation = template.translated_contents.get(language='en')

    # No need to create the attachment again since the fixture already does that
    recipients = ['mrec1@gmail.com', 'mrec2@gmail.com']
    sender = 'from@gmail.com'
    context = {'test': 'val'}
    email = send(
        sender=sender,
        recipients=recipients,
        template=template,
        priority='medium',
        commit=True,
        context=context,
        language='en',
        backend='default',
        attachments={'def.txt': ContentFile(b'Some data...')}
    )

    assert Attachment.objects.count() == 2  # Should include default.txt and en_attachment.txt

    assert email.attachments.count() == 2

    attachments = list(Attachment.objects.all())
    assert len(attachments) == 2
    assert sorted([attachments[0].name, attachments[1].name]) == sorted(['def.txt', 'en_attachment.txt'])

    # Test sending to a different language
    email = send(
        sender=sender,
        recipients=recipients,
        template=template,
        priority='medium',
        commit=True,
        context=context,
        language='de',
        backend='default',
        attachments={'default.txt': ContentFile(b'Some data...')}
    )

    assert Attachment.objects.count() == 3  # Expecting default.txt + en_attachment.txt + de_attachment.txt
    assert (attachments := email.attachments.all()).count() == 1  # Should only be the default.txt

    assert attachments[0].name == 'default.txt'


@pytest.mark.django_db
def test_many_extra_attachments(settings, template_with_extra_attachments):
    # Retrieve the template with the extra attachments already set up
    template = template_with_extra_attachments

    de_translation = template.translated_contents.get(language='de')
    de_path = settings.BASE_DIR / 'demoapp' / 'tests' / 'assets' / 'de_attachment.txt'

    with open(de_path, 'rb') as f:
        file = ContentFile(f.read(), name='de_attachment.txt')
        de_attachment = Attachment.objects.create(
            file=file,
            name='de_attachment.txt',
            mimetype='text/plain'
        )
    de_translation.extra_attachments.set([de_attachment])
    de_translation.save()

    john = EmailAddress.objects.create(email='john@email.com')
    marry = EmailAddress.objects.create(email='marry@email.com', preferred_language='de')

    emails = send_many(
        recipients=[john, marry],
        template='test_template',
        attachments={'defau.txt': ContentFile(b'Some data...')}
    )

    assert emails[0].language == 'en'
    assert emails[1].language == 'de'

    assert len((en_attachments := list(emails[0].attachments.all()))) == 2  # Check English attachments
    assert len((de_attachments := list(emails[1].attachments.all()))) == 2  # Check German attachments

    assert sorted([en_attachments[0].name, en_attachments[1].name]) == sorted(['en_attachment.txt','defau.txt'])
    assert sorted([de_attachments[0].name, de_attachments[1].name]) == sorted(['de_attachment.txt','defau.txt'])
