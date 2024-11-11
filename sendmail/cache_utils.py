from django.conf import settings

from sendmail import cache
from sendmail.parser import process_template


def get_placeholders(template, language=''):
    """
    Function that returns an email template instance, from cache or DB.
    """
    use_cache = getattr(settings, 'SENDMAIL_CACHE', False)
    if use_cache:
        use_cache = getattr(settings, 'SENDMAIL_PLACEHOLDERS_CACHE', True)
    if not use_cache:
        return template.contents.filter(language=language,
                                        base_file=template.base_file)
    else:
        composite_name = '%s:%s:%s' % (template.name, language, template.base_file)
        placeholders = cache.get(composite_name, category='placeholders')
        print(composite_name)
        if placeholders is None:
            print('Placeholders from db')
            placeholders = template.contents.filter(language=language,
                                                    base_file=template.base_file)
            cache.set(composite_name, list(placeholders), category='placeholders')
        else:
            print('Placeholders from cache')

        return placeholders


def get_placeholder_names(template):
    use_cache = getattr(settings, 'SENDMAIL_CACHE', True)
    if use_cache:
        use_cache = getattr(settings, 'SENDMAIL_PLACEHOLDERS_NAME_CACHE', True)

    if not use_cache:
        return set(process_template(template.base_file))

    composite_name = '%s' % template.base_file

    placeholders_names = cache.get(composite_name, category='names', template_path=template.base_file)

    if placeholders_names is None:
        placeholders_names = process_template(template.base_file)
        print('PARSED')
        cache.set(composite_name, list(placeholders_names), category='names', template_path=template.base_file)
    else:
        print('CACHED')

    return set(placeholders_names)
