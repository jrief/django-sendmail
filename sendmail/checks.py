from django.conf import settings
from django.core.checks import Warning, register

from sendmail.settings import get_cache_backend


@register
def check_cache_backend(app_configs, **kwargs):
    """
    Check the cache backend configuration for the application.

    This function assesses the settings for sending mail caches to ensure that a
    centralized cache backend is utilized if placeholders cache is set to True.
    It will warn the user if a suitable centralized cache backend is not configured.

    Parameters:
        app_configs: This is a placeholder for any app configurations that might be
                     needed for the check. It is currently not used.
        **kwargs: Additional keyword arguments that remain unused in the function.

    Returns:
        A list containing Warning objects if the cache configuration is considered
        suboptimal; otherwise, an empty list is returned.
    """
    use_cache = getattr(settings, 'SENDMAIL_CACHE', True)
    if use_cache:
        use_cache = getattr(settings, 'SENDMAIL_PLACEHOLDERS_CACHE', False)

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
