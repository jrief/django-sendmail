from django.conf import settings

from sendmail import cache
from sendmail.parser import process_template


def get_placeholders(template, language=''):
    """
    Function that returns placeholders for given template and language, from cache or DB.
    """
    use_cache = getattr(settings, 'SENDMAIL_CACHE', True)
    if use_cache:
        use_cache = getattr(settings, 'SENDMAIL_PLACEHOLDERS_CACHE', False)
    if not use_cache:
        return template.contents.filter(language=language,
                                        used_template_file=template.template_file)
    else:
        composite_name = '%s:%s:%s' % (template.name, language, template.template_file)
        placeholders = cache.get(composite_name, category='placeholders')
        if placeholders is None:
            placeholders = template.contents.filter(language=language,
                                                    used_template_file=template.template_file)
            cache.set(composite_name, list(placeholders), category='placeholders')

        return placeholders


def get_placeholder_names(template):
    use_cache = getattr(settings, 'SENDMAIL_CACHE', True)
    if use_cache:
        use_cache = getattr(settings, 'SENDMAIL_PLACEHOLDERS_NAME_CACHE', False)

    if not use_cache:
        return set(process_template(template.template_file))

    composite_name = '%s' % template.template_file

    placeholders_names = cache.get(composite_name, category='names')

    if placeholders_names is None:
        placeholders_names = process_template(template.template_file)
        cache.set(composite_name, list(placeholders_names), category='names')

    return set(placeholders_names)
