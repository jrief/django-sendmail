
from django.template.defaultfilters import slugify
from django.template.loader import get_template
from pathlib import Path
from .settings import get_cache_backend

# Stripped down version of caching functions from django-dbtemplates
# https://github.com/jezdez/django-dbtemplates/blob/develop/dbtemplates/utils/cache.py
cache_backend = get_cache_backend()


def get_cache_key(name, category='template', template_path=None):
    """
    Prefixes and slugify the key name
    """
    timestamp = ""
    if template_path:
        full_path = Path(get_template(template_path).origin.name)
        if full_path.exists():
            timestamp = str(int(full_path.stat().st_mtime))

    print(f"Timestamp: {timestamp}")

    return f'sendmail:{category}:{slugify(name)}:{timestamp}'


def set(name, content, category='template', template_path=None):
    return cache_backend.set(get_cache_key(name, category, template_path), content)


def get(name, category='template', template_path=None):
    return cache_backend.get(get_cache_key(name, category, template_path))


def delete(name, category='template', template_path=None):
    return cache_backend.delete(get_cache_key(name, category, template_path))
