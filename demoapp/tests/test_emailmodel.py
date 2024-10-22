from email.mime.image import MIMEImage

import pytest
from sendmail.models import EmailModel
from sendmail.models import STATUS, PRIORITY, EmailAddress, render_message
from sendmail.utils import set_recipients
from django.core.mail import EmailMessage, EmailMultiAlternatives
from sendmail.settings import get_template_engine
#from django.conf import settings


@pytest.fixture
def recipients():
    return [EmailAddress.objects.create(email=f"{i}@email.com") for i in range(5)]


@pytest.fixture
def simple_email(recipients):
    email = EmailModel.objects.create(
        from_email='from@email.com',
        subject='Test subject #id#',
        message='Test message #id#',
        html_message="<h1>Testing mail to #recipient.first_name#</h1>",
        status=STATUS.queued,
        priority=PRIORITY.medium,
        language='en'
    )
    set_recipients(email, recipients)

    return email


def get_header(image: MIMEImage, header: str):
    for head in image._headers:
        if head[0] == header:
            return head[1]


@pytest.mark.django_db
def test_no_cache(simple_email):
    assert not simple_email._cached_email_message


@pytest.mark.django_db
def test_get_message(settings, simple_email):
    email = simple_email.get_message_object(simple_email.html_message,
                                            simple_email.message,
                                            headers=None,
                                            subject='Test rendered subject',
                                            connection='default',
                                            multipart_template=None)

    assert isinstance(email, EmailMultiAlternatives)

    assert email.to == [str(rec) for rec in simple_email.recipients.all()]

    assert email.subject == 'Test rendered subject'

    assert email.from_email == 'from@email.com'

    assert len(email.alternatives) == 1

    assert email.alternatives[0] == (simple_email.html_message, 'text/html')
    assert email.body == simple_email.message

    email = simple_email.get_message_object(simple_email.html_message,
                                            plaintext_message=None,
                                            headers=None,
                                            subject='Test rendered subject',
                                            connection='default',
                                            multipart_template=None)

    assert email.content_subtype == 'html'
    assert email.body == simple_email.html_message

    email = simple_email.get_message_object(html_message=None,
                                            plaintext_message=simple_email.message,
                                            headers=None,
                                            subject='Test rendered subject',
                                            connection='default',
                                            multipart_template=None)

    assert isinstance(email, EmailMessage)

    html_with_inlines = (f"{{% load sendmail %}}\n "
                         f"<img src='{{% inline_image '{settings.BASE_DIR / 'demoapp' / 'tests' / 'assets' / 'logo.png'}'%}}'"
                         f"{simple_email.html_message}")
    simple_email.html_message = html_with_inlines

    engine = get_template_engine()
    multipart_template = engine.from_string(simple_email.html_message)

    templated_email = simple_email.get_message_object(html_message=html_with_inlines,
                                                      plaintext_message=None,
                                                      subject='Test rendered subject',
                                                      connection='default',
                                                      multipart_template=multipart_template,
                                                      headers=None, )

    assert templated_email.body.count('cid:') == 1

    cid_block = templated_email.body.split('cid:')[1]

    cid = cid_block.split("\'")[0]

    assert len(templated_email.attachments) == 1

    assert isinstance(image := templated_email.attachments[0], MIMEImage)

    assert get_header(image, 'Content-Type') == 'image/png'

    assert get_header(image, 'Content-Disposition') == f'inline; filename="{cid}"'

    assert get_header(image, 'Content-ID') == f"<{cid}>"


@pytest.mark.django_db
def test_render_message():
    test_message = 'Test message'
    assert render_message(test_message, {}) == 'Test message'

    assert render_message('Test message#c#', {}) == 'Test message#c#'

    test_context = {
        'a': 10,
        'b': 20,
        'c': 'Hello',
        'disallowed_script': '<script>alert("Hello")</script>'
    }

    test_message_with_context = render_message('#c# I am #b#', test_context)

    assert test_message_with_context == 'Hello I am 20'

    assert render_message('#disallowed_script#', test_context) == ''

    assert render_message('##c##', test_context) == '#Hello#'

    test_recipient = EmailAddress(
        first_name='John',
        last_name='Doe',
        email='test@email.com',
        preferred_language='en',
        gender='male',
        is_blocked=False
    )

    test_message = '<p>Test message #recipient.first_name# #recipient.last_name#</p>'

    assert render_message(test_message, {'recipient': test_recipient}) == ('<p>Test message John '
                                                                           'Doe</p>')

    assert render_message(test_message, context={'recipient': test_recipient, 'recipient.first_name': 'Alisa'}) == (
        '<p>Test message Alisa Doe</p>')


@pytest.mark.django_db
def test__str(simple_email, recipients):
    assert str(simple_email) == str([str(rec) for rec in recipients])


