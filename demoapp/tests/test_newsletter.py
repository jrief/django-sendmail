import pytest
from sendmail.models.recipients_list import RecipientsList
from sendmail.models.newsletter import Newsletter
from sendmail.models.emailaddress import EmailAddress

@pytest.fixture
def recipient_list():
    addresses = [EmailAddress(email=f'{i}@example.com') for i in range(5)]
