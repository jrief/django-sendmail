from datetime import timedelta

from django.conf import settings as django_settings
from django.core.mail.utils import DNS_NAME


class Settings:
    @property
    def SENDMAIL(self):
        config = getattr(django_settings, 'SENDMAIL', {})
        config.setdefault('BATCH_SIZE', 100)
        config.setdefault('CELERY_ENABLED', False)
        config.setdefault('DEFAULT_PRIORITY', 'medium')
        config.setdefault('LOG_LEVEL', 'medium')
        config.setdefault('SENDING_ORDER', ['-priority'])
        config.setdefault('TEMPLATE_ENGINE', 'django')
        config.setdefault('MAX_RETRIES', 0)
        config.setdefault('RETRY_INTERVAL', timedelta(minutes=15))
        config.setdefault('MESSAGE_ID_ENABLED', True)
        config.setdefault('MESSAGE_ID_FQDN', DNS_NAME)
        return config

    @property
    def EMAIL_ADDRESS_MODEL(self):
        return getattr(django_settings, 'EMAIL_ADDRESS_MODEL', 'sendmail.model.EmailAddress')


settings = Settings()
