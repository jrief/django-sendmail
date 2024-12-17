import pytest
from django.core.exceptions import ValidationError

from sendmail.mail import _send_bulk
from sendmail.models import PlaceholderContent
from sendmail.models.emailaddress import EmailAddress
from sendmail.models.emailmodel import STATUS, EmailModel
from sendmail.models.newsletter import RESULT
from sendmail.models.newsletter import STATUS as Newsletter_STATUS
from sendmail.models.newsletter import Newsletter
from sendmail.models.recipients_list import RecipientsList
from sendmail.utils import set_recipients, update_newsletter_counts


@pytest.fixture
def recipient_list():
    addresses = [EmailAddress.objects.create(email=f'{i}@example.com',
                                             first_name=f"Name_{i}",
                                             last_name=f"Last_name_{i}")
                 for i in range(5)]

    addresses[0].preferred_language = 'de'
    addresses[0].save()
    rec_list = RecipientsList.objects.create(name='students')
    rec_list.recipients.set(addresses)
    return rec_list


@pytest.fixture
def template_newsletter(recipient_list, template):
    placeholder1 = PlaceholderContent.objects.get(placeholder_name='test1', language='en')
    placeholder2 = PlaceholderContent.objects.get(placeholder_name='test2', language='en')

    placeholder1.content = 'This is a #var1#'
    placeholder1.save()

    placeholder2.content = 'This is a #var2# and #var1# and #new.var1#'
    placeholder2.save()
    news = Newsletter.objects.create(name='greeting', to_recipients=recipient_list, emailmerge=template)

    return news

@pytest.fixture
def duplicate_newsletter(recipient_list, template):
    placeholder1 = PlaceholderContent.objects.get(placeholder_name='test1', language='en')
    placeholder2 = PlaceholderContent.objects.get(placeholder_name='test2', language='en')

    placeholder1.content = 'This is a #var1#'
    placeholder1.save()

    placeholder2.content = 'This is a #var2# and #var1# and #new.var1#'
    placeholder2.save()
    news = Newsletter.objects.create(name='duplicate', to_recipients=recipient_list, emailmerge=template)

    return news




@pytest.mark.django_db
def test_newsletter_creation(template_newsletter):
    newsletter = template_newsletter
    assert str(newsletter) == 'greeting'
    assert newsletter.to_recipients.recipients.count() == 5
    assert newsletter.emailmerge.name == 'test_template'


@pytest.mark.django_db
def test_construct_context(template_newsletter):
    assert template_newsletter.context == {'var2': '', 'test_var': '', 'var1': '', 'new.var1': ''}



@pytest.mark.django_db
def test_template_send(template_newsletter):
    created_emails = template_newsletter.create()

    assert len(created_emails) == 5

    assert all([email.status == STATUS.queued for email in created_emails])

    assert [email.recipients.first().email for email in created_emails] == [f'{i}@example.com' for i in range(5)]

    assert list(created_emails) == list(EmailModel.objects.all())

    created_emails = list(created_emails)

    assert created_emails[0].subject == 'DE test_subject'

    assert created_emails[1].subject == 'template_subject'

    assert created_emails[0].context == {
        'new.var1': '',
        'recipient': 1,
        'test_var': '',
        'var1': '',
        'var2': '',
    }

    assert created_emails[0].recipients.first() == EmailAddress.objects.get(pk=1)

    assert created_emails[1].context == {
        'new.var1': '',
        'recipient': 2,
        'test_var': '',
        'var1': '',
        'var2': '',
    }

    assert created_emails[1].recipients.first() == EmailAddress.objects.get(pk=2)



@pytest.mark.django_db
def test_update_newsletter_counter(template_newsletter, duplicate_newsletter):
    recipients = [EmailAddress.objects.create(email=f"{i}@exmaple.com") for i in range(10)]

    news1 = template_newsletter
    assert news1.status == Newsletter_STATUS.draft

    news2 = duplicate_newsletter
    assert news2.status == Newsletter_STATUS.draft

    success_emails = [EmailModel.objects.create(from_email='test@ex.com',language='en', status=STATUS.sent) for _ in range(7)]
    failed_emails = [EmailModel.objects.create(from_email='ex@test.com', language='en', status=STATUS.failed) for _ in range(7, 10)]
    emails = [*success_emails, *failed_emails]
    failed_emails = [(email, str(ValidationError)) for email in failed_emails]
    for inx, (email, recipient) in enumerate(zip(emails, recipients)):
        set_recipients(email, recipients)
        if inx > 5:
            email.newsletter = news1
        else:
            email.newsletter = news2
        email.save()

    assert update_newsletter_counts(emails, success_emails, failed_emails) == {1: {'failed': 3, 'sent': 1}, 2: {'failed': 0, 'sent': 6}}

    news1.refresh_from_db()
    news2.refresh_from_db()

    assert news1.sent_emails == 1
    assert news2.sent_emails == 6

    assert news1.failed_emails == 3
    assert news2.failed_emails == 0


@pytest.mark.django_db
def test_success_status(template_newsletter):
    assert template_newsletter.status == Newsletter_STATUS.draft

    emails = template_newsletter.create()

    assert template_newsletter.status == Newsletter_STATUS.queued

    _send_bulk(emails, False)

    template_newsletter.refresh_from_db()

    assert template_newsletter.status == Newsletter_STATUS.completed

    assert template_newsletter.result == RESULT.success

@pytest.mark.django_db
def test_failed_status(template_newsletter):
    assert template_newsletter.status == Newsletter_STATUS.draft

    emails = template_newsletter.create()

    for email in emails:
        email.backend_alias = 'error'
        email.save()

    assert template_newsletter.status == Newsletter_STATUS.queued

    _send_bulk(emails, False)

    template_newsletter.refresh_from_db()

    assert template_newsletter.status == Newsletter_STATUS.completed

    assert template_newsletter.result == RESULT.failed

@pytest.mark.django_db
def test_partial_status(template_newsletter):
    assert template_newsletter.status == Newsletter_STATUS.draft

    emails = template_newsletter.create()

    for email in emails:
        if email in emails[:1]:
            email.backend_alias = 'error'
        email.save()

    assert template_newsletter.status == Newsletter_STATUS.queued

    _send_bulk(emails, False)

    template_newsletter.refresh_from_db()

    assert template_newsletter.status == Newsletter_STATUS.completed

    assert template_newsletter.sent_emails == 4
    assert template_newsletter.failed_emails == 1

    assert template_newsletter.result == RESULT.partial




