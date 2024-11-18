from django.conf import settings
from django.core.checks import Warning, register

from sendmail.settings import get_cache_backend


@register
def check_cache_backend(app_configs, **kwargs):
    use_cache = getattr(settings, 'SENDMAIL_CACHE', True)
    if use_cache:
        use_cache = getattr(settings, 'SENDMAIL_PLACEHOLDERS_CACHE', True)

        if use_cache:
            cls = get_cache_backend().__class__.__name__

            centralized_caches = [
                'RedisCache',
                'MemcachedCache',
                'PyLibMCCache'
            ]

            if cls not in centralized_caches:
                return [
                    Warning(
                        "CACHE_PLACEHOLDERS is set to True, but a centralized cache "
                        "backend (e.g., Redis or Memcached) is not being used. "
                        "Please configure a centralized cache backend in settings.py.",
                        id="sendmail.W001"
                    )
                ]
    return []
