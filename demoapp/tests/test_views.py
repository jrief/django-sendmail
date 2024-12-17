import datetime
from urllib.parse import quote

import pytest
from django.core.files.storage import default_storage
from django.utils import timezone

from sendmail.models.emailmodel import PRIORITY, STATUS, EmailModel


@pytest.fixture
def simple_email():
    email = EmailModel.objects.create(
        from_email='from@email.com',
        subject='Test subject #id#',
        message='Test message #id#',
        html_message="<h1>Testing mail to #recipient.first_name#</h1>",
        status=STATUS.queued,
        priority=PRIORITY.medium,
        language='en'
    )

    return email

@pytest.mark.django_db
def test_track(settings, simple_email, client, collectstatic):
    settings.DEBUG = True
    assert simple_email.opened_at is None

    # Test static with DEBUG
    response = client.get(f'/sendmail/track/{simple_email.id}/images/static_logo.jpg')
    assert response.status_code == 200
    simple_email.refresh_from_db()
    assert isinstance(simple_email.opened_at, datetime.datetime)

    now = timezone.now()

    assert (now - simple_email.opened_at).total_seconds() < 1

    # Not found in static with DEBUG
    response = client.get(f'/sendmail/track/{simple_email.id}/images/not_valid.png')
    assert response.status_code == 404
    assert response.content == b'Image not found'


    settings.DEBUG = False
    settings.MEDIA_ROOT = (settings.BASE_DIR / 'demoapp' / 'tests' / 'assets')

    # Test media
    response = client.get(f'/sendmail/track/{simple_email.id}/media_logo.png')
    assert response.status_code == 200
    with default_storage.open(settings.MEDIA_ROOT / 'media_logo.png') as f:
        assert b''.join(response.streaming_content) == f.read()


    # Test Staticfiles
    response = client.get(f'/sendmail/track/{simple_email.id}/images/static_logo.jpg')
    assert response.status_code == 200

    # Not found in staticfiles without DEBUG
    response = client.get(f'/sendmail/track/{simple_email.id}/images/not_valid.png')
    assert response.status_code == 404


@pytest.mark.django_db
def test_click(simple_email, client):
    assert simple_email.clicked_at is None
    target_url = quote('https://google.com')
    response = client.get(f'/sendmail/click/{simple_email.id}/?target_uri={target_url}')
    assert response.status_code == 302
    assert response['Location'] == 'https://google.com'
    simple_email.refresh_from_db()
    assert isinstance(simple_email.clicked_at, datetime.datetime)
    now = timezone.now()

    assert (now - simple_email.clicked_at).total_seconds() < 1

    response = client.get(f'/sendmail/click/{simple_email.id}/')

    assert response.status_code == 400

    response = client.get(f'/sendmail/click/{simple_email.id}/?target_uri=hts://google.com')

    assert response.status_code == 400
