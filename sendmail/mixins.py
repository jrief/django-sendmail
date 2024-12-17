from sendmail.settings import get_email_address_setting


class SwappableMetaMixin:

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not hasattr(cls, 'Meta'):
            cls.Meta = type('Meta', (), {})

        cls.Meta.swappable = get_email_address_setting()
