from django.template.defaultfilters import slugify

from sendmail.settings import get_cache_backend, get_placeholders_names_timeout

# Stripped down version of caching functions from django-dbtemplates
# https://github.com/jezdez/django-dbtemplates/blob/develop/dbtemplates/utils/cache.py
cache_backend = get_cache_backend()


def get_cache_key(name, category='template'):
    """
    Prefixes and slugify the key name
    """

    return f'sendmail:{category}:{slugify(name)}'


def set(name, content, category='template'):
    if category == 'names' and (timeout := get_placeholders_names_timeout()):
        return cache_backend.set(get_cache_key(name, category), content, timeout=timeout)
    return cache_backend.set(get_cache_key(name, category), content)


def get(name, category='template'):
    return cache_backend.get(get_cache_key(name, category))


def delete(name, category='template'):
    return cache_backend.delete(get_cache_key(name, category))

