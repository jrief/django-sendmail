from django.conf import settings
from sendmail import cache


def get_placeholders(template, language=''):
    """
    Function that returns an email template instance, from cache or DB.
    """
    use_cache = getattr(settings, 'POST_OFFICE_CACHE', False)
    if use_cache:
        use_cache = getattr(settings, 'POST_OFFICE_PLACEHOLDERS_CACHE', True)
    if not use_cache:
        return template.contents.filter(language=language,
                                        base_file=template.base_file)
    else:
        composite_name = 'placeholders %s:%s:%s' % (template.name, language, template.base_file)
        placeholders = cache.get(composite_name)
        print(composite_name)
        if placeholders is None:
            print('Placeholders from db')
            placeholders = template.contents.filter(language=language,
                                                    base_file=template.base_file)
            cache.set(composite_name, list(placeholders))
        else:
            print('Placeholders from cache')

        return placeholders
