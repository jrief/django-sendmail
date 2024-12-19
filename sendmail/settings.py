import datetime
import warnings

from django.apps import apps
from django.conf import settings
from django.core.cache import caches
from django.core.cache.backends.base import InvalidCacheBackendError
from django.core.files.storage import InvalidStorageError, default_storage, storages
from django.core.mail.utils import DNS_NAME
from django.template import engines as template_engines


def get_attachments_storage():
    try:
        storage = storages['sendmail_attachments']
    except InvalidStorageError:
        storage = default_storage

    return storage


def get_backend(alias='default'):
    return get_available_backends()[alias]


def get_available_backends():
    """Returns a dictionary of defined backend classes. For example:
    {
        'default': 'django.core.mail.backends.smtp.EmailBackend',
        'locmem': 'django.core.mail.backends.locmem.EmailBackend',
    }
    """
    backends = get_config().get('BACKENDS', {})

    if backends:
        return backends

    # Try to get backend settings from old style
    # SENDMAIL = {
    #     'EMAIL_BACKEND': 'mybackend'
    # }
    backend = get_config().get('EMAIL_BACKEND')
    if backend:
        warnings.warn('Please use the new SENDMAIL["BACKENDS"] settings', DeprecationWarning)

        backends['default'] = backend
        return backends

    # Fall back to Django's EMAIL_BACKEND definition
    backends['default'] = getattr(settings, 'EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')

    # If EMAIL_BACKEND is set to use PostOfficeBackend
    # and SENDMAIL_BACKEND is not set, fall back to SMTP
    if 'sendmail.EmailBackend' in backends['default']:
        backends['default'] = 'django.core.mail.backends.smtp.EmailBackend'

    return backends


def get_cache_backend():
    if hasattr(settings, 'CACHES'):
        if 'sendmail' in settings.CACHES:
            return caches['sendmail']
        else:
            # Sometimes this raises InvalidCacheBackendError, which is ok too
            try:
                return caches['default']
            except InvalidCacheBackendError:
                pass
    return None


def get_placeholders_names_timeout():
    return getattr(settings, 'PLACEHOLDERS_NAMES_CACHE_TIMEOUT', None)


def get_config():
    """
    Returns Post Office's configuration in dictionary format. e.g:
    POST_OFFICE = {
        'BATCH_SIZE': 1000
    }
    """
    return getattr(settings, 'SENDMAIL', {})


def get_languages_list():
    if settings.USE_I18N:
        lang_conf = getattr(settings, 'LANGUAGES', [])
        return [lang[0] for lang in lang_conf]
    else:
        return [get_default_language(), ]


def get_default_language():
    return settings.LANGUAGE_CODE


def get_batch_size():
    return get_config().get('BATCH_SIZE', 100)


def get_celery_enabled():
    return get_config().get('CELERY_ENABLED', False)


def get_default_priority():
    return get_config().get('DEFAULT_PRIORITY', 'medium')


def get_log_level():
    return get_config().get('LOG_LEVEL', 2)


def get_sending_order():
    return get_config().get('SENDING_ORDER', ['-priority'])


def get_template_engine():
    using = get_config().get('TEMPLATE_ENGINE', 'sendmail')
    return template_engines[using]


def get_email_address_model():
    model_name = get_email_address_setting()
    return apps.get_model(model_name)


def get_email_address_setting():
    return getattr(settings, 'EMAIL_ADDRESS_MODEL', 'sendmail.EmailAddress')


# def get_override_recipients():
#     return get_config().get('OVERRIDE_RECIPIENTS', None)

def get_break_after_batch():
    return get_config().get('BREAK_AFTER_BATCH', False)


def get_max_retries():
    return get_config().get('MAX_RETRIES', 0)


def get_retry_timedelta():
    return get_config().get('RETRY_INTERVAL', datetime.timedelta(minutes=15))


def get_message_id_enabled():
    return get_config().get('MESSAGE_ID_ENABLED', False)


def get_message_id_fqdn():
    return get_config().get('MESSAGE_ID_FQDN', DNS_NAME)


# BATCH_DELIVERY_TIMEOUT defaults to 180 seconds (3 minutes)
def get_batch_delivery_timeout():
    return get_config().get('BATCH_DELIVERY_TIMEOUT', 180)


def get_email_templates():
    return get_config().get('EMAIL_TEMPLATES', [])

def get_tracking_enabled():
    return get_config().get('TRACKING_ENABLED', False)

def get_tracking_domain():
    return get_config().get('TRACKING_DOMAIN', 'http://127.0.0.1:8000')
