from typing import List
import requests

from demoapp.tests.conftest import email_testing
from sendmail.mail import send, send_many, _send_bulk
import pytest
from sendmail.models.emailaddress import EmailAddress
from sendmail.models.emailmerge import EmailMergeModel, PlaceholderContent
import tempfile
from multiprocessing import Pool
from sendmail.utils import get_recipients_objects

from sendmail.utils import split_emails


@pytest.fixture
def recipient():
    return EmailAddress.objects.create(email='john@gmail.com',
                                       first_name='John',
                                       last_name='Doe',
                                       gender='male',
                                       preferred_language='en')


@pytest.fixture
def template():
    template_context = EmailMergeModel.objects.create(
        base_file='test/context_test.html',
        name='test_name',
        description='test_description',
    )

    en_translation = template_context.translated_contents.get(language='en')
    en_translation.subject = 'test_subject'
    en_translation.content = 'test_content'
    en_translation.save()

    de_translation = template_context.translated_contents.get(language='de')
    de_translation.subject = 'DE test_subject'
    de_translation.content = 'DE test_content'

    de_translation.save()

    return template_context


# def get_all_messages(limit=None):
#     if not limit:
#         data = requests.get('http://127.0.0.1:8025/api/v1/messages').json()
#
#     else:
#         data = requests.get(f'http://127.0.0.1:8025/api/v1/messages?limit={limit}').json()
#
#     return data['messages'], data['messages_count']
#
#
# def get_message(message_id):
#     return requests.get(f'http://127.0.0.1:8025/api/v1/message/{message_id}').json()

# def get_attachment(message_id, partid):
#     return requests.get(f'http://127.0.0.1:8025/api/v1/message/{message_id}/part/{partid}').content


def extract_html_message_for_recipient(recipient_email, email_testing):
    for message in email_testing.all_messages():
        first_recipient = extract_recipients(message)[0]
        if first_recipient == recipient_email:
            return message['HTML'].replace('\n', '').replace('\t', '').replace('\r', '').strip()


def extract_recipients(email_message, recipient_type='To'):
    return [rec['Address'] for rec in email_message[recipient_type]]


@pytest.mark.django_db
def test_index(settings, email_testing, recipient):
    email_testing.delete_all()
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(b'This is a sample message.')
        tmp.seek(0)
        email = send(
            ['john@example.com', 'next@example.com'],
            cc=['cc1@email.com', 'cc2@email.com'],
            bcc=['bcc1@email.com', 'bcc2@email.com'],
            subject='Letter #id#',
            context={'id': 1},
            html_message="Hi there #recipient.first_name#",
            priority='now',
            backend='smtp',
            attachments={'test.txt': tmp},
        )
    messages = email_testing.all_messages()
    assert messages['count'] == 1
    id = messages['messages']['ID']
    message_info = email_testing.get_message(id)
    assert message_info['MessageID'] == email.message_id.strip('<').strip('>')

    to = message_info['To']
    assert len(to) == 2
    assert to[0]['Address'] == 'john@example.com'
    assert to[1]['Address'] == 'next@example.com'

    cc = message_info['Cc']
    assert len(cc) == 2
    assert cc[0]['Address'] == 'cc1@email.com'
    assert cc[1]['Address'] == 'cc2@email.com'

    bcc = message_info['Bcc']
    assert len(bcc) == 2
    assert bcc[0]['Address'] == 'bcc1@email.com'
    assert bcc[1]['Address'] == 'bcc2@email.com'

    from_ = message_info['From']
    assert from_['Address'] == settings.DEFAULT_FROM_EMAIL

    assert message_info['Subject'] == 'Letter 1'
    assert message_info['Text'] == 'Hi there John'

    assert len(message_info['Attachments']) == 1

    attachment = message_info['Attachments'][0]

    part_id = attachment['PartID']
    assert attachment['FileName'] == 'test.txt'
    assert attachment['ContentType'] == 'text/plain'
    assert email_testing(id, part_id).content == b'This is a sample message.'


@pytest.mark.django_db
def test_send_many(settings, email_testing, template):
    email_testing.delete_all()
    john = EmailAddress.objects.create(
        email='john@example.com',
        first_name='John',
        last_name='Doe',
        gender='male',
        preferred_language='en',
    )
    gudrun = EmailAddress.objects.create(
        email='gudrun@example.com',
        first_name='Gudrun',
        last_name='Hauser',
        gender='female',
        preferred_language='de',
    )
    ben = EmailAddress.objects.create(
        email='ben@example.com',
        first_name='Ben',
        last_name='White',
        gender='other',
        is_blocked=True,
    )
    emails = send_many(
        recipients=[john, gudrun, ben],
        template=template,
        context={'test_var': 'test_value'},
        backend='smtp',
    )

    _send_bulk(emails, uses_multiprocessing=False)

    messages = email_testing.all_messages()
    assert messages['count'] == 2

    message_infos = []
    all_recipients = set()

    for message in messages['messages']:
        message_info = email_testing.get_message(message['ID'])
        message_infos.append(message_info)
        recipients = extract_recipients(message_info)
        assert len(recipients) == 1
        all_recipients.add(recipients[0])

    assert all_recipients == {john.email, gudrun.email}
    assert sorted([info['Subject'] for info in message_infos]) == sorted(['test_subject', 'DE test_subject'])
    assert sorted([info['Text'] for info in message_infos]) == sorted(['test_content', 'DE test_content'])

    # john_msg = get_html_message_for_recipient('john@gmail.com', messages)
    # assert john_msg.count('John') > 0
    # assert john_msg.count('Doe') > 0
    # assert not john_msg.count('Marry')
    # assert not john_msg.count('Ben')
    # assert john_msg.count('test_val') == 1

    placeholder = PlaceholderContent.objects.get(placeholder_name='test1', language='en')
    placeholder.content = '#test_var#'
    placeholder.save()

    emails = send_many(
        recipients=[john, gudrun, ben],
        template=template,
        context={'test_var': 'test_value'},
        backend='smtp',
    )

    _send_bulk(emails, uses_multiprocessing=False)

    messages = email_testing.all_messages()
    assert messages['count'] == 4

    # assert get_html_message_for_recipient('john@gmail.com', messages).count('test_value') == 2
    # assert get_html_message_for_recipient('marry@gmail.com', messages).count('test_value') == 1
    # assert get_html_message_for_recipient('john@gmail.com', messages).count('#test_var#') == 0
    # assert get_html_message_for_recipient('marry@gmail.com', messages).count('#test_var#') == 0


@pytest.mark.skip
@pytest.mark.django_db
def test_simulate_mp(email_testing, template):
    recipients = [f"{i}@email.com" for i in range(50)]
    recipient_objects = get_recipients_objects(recipients)
    for index, recipient in enumerate(recipient_objects):
        recipient.first_name = f"Recipient {index}"
        if index > 25:
            recipient.preferred_language = 'de'
        recipient.save()

    emails = send_many(recipients=recipients, template=template, context={'test_var': 'test_value'}, backend='smtp')
    pool = Pool(processes=3)

    email_lists = split_emails(emails)

    tasks = []

    for mails in email_lists:
        tasks.append(pool.apply_async(_send_bulk, args=(mails, False)))

    results = []

    for task in tasks:
        results.append(task.get())

    pool.terminate()
    pool.join()

    assert results == [(50, 0, 0)]

    messages = email_testing.all_messages(limit=51)
    assert messages['count'] == 50
    seen = set()

    for recipient in recipients:
        num = int(recipient.split('@')[0])
        html = get_html_message_for_recipient(recipient, messages)
        assert html, recipient

        assert recipient not in seen
        seen.add(recipient)

        assert html.count(f'Recipient {num}') == 1

        if num > 25:
            assert html.count('Language: de') == 2
            assert html.count('Language: en') == 0

        else:
            assert html.count('Language: de') == 0
            assert html.count('Language: en') == 2
