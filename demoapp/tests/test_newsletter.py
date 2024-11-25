import pytest
from django.core.exceptions import ValidationError

from sendmail.models import PlaceholderContent
from sendmail.models.recipients_list import RecipientsList
from sendmail.models.newsletter import Newsletter
from sendmail.models.emailaddress import EmailAddress
from sendmail.models.emailmodel import STATUS, EmailModel


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
def basic_newsletter(recipient_list):
    news = Newsletter.objects.create(name='basic',
                                     to_recipients=recipient_list,
                                     subject=f"#subj# to #recipient.first_name#",
                                     html_message='''
                                     <h1>Dear #salute# #recipient.last_name# </h1>
                                     ''')

    return news


@pytest.mark.django_db
def test_newsletter_creation(template_newsletter):
    newsletter = template_newsletter
    assert str(newsletter) == 'greeting'
    assert newsletter.to_recipients.recipients.count() == 5
    assert newsletter.emailmerge.name == 'test_template'


@pytest.mark.django_db
def test_construct_context(template_newsletter, basic_newsletter):
    assert template_newsletter.context == {'var2': '', 'test_var': '', 'var1': '', 'new.var1': ''}

    assert basic_newsletter.context == {'subj': '', 'salute': ''}


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
def test_basic_send(basic_newsletter):
    emails = basic_newsletter.create()

    assert len(emails) == 5

    created_emails = list(emails)

    assert created_emails[0].subject == '#subj# to #recipient.first_name#'

    assert created_emails[0].context == {
        'recipient': 1,
        'salute': '',
        'subj': '',
    }

    assert created_emails[0].recipients.first() == EmailAddress.objects.get(pk=1)


@pytest.mark.django_db
def test_clean(template_newsletter):
    template_newsletter.clean()

    template_newsletter.subject = 'Subj'

    with pytest.raises(ValidationError):
        template_newsletter.clean()

    template_newsletter.subject = None

    template_newsletter.message = 'Message'

    with pytest.raises(ValidationError):
        template_newsletter.clean()

    template_newsletter.message = None

    template_newsletter.html_message = 'HTML'

    with pytest.raises(ValidationError):
        template_newsletter.clean()
