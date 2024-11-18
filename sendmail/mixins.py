from sendmail.settings import get_email_address_setting


class SwappableMetaMixin:
    class Meta:
        swappable = get_email_address_setting()