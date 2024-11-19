import pathlib

from django.conf import settings
from django.utils.safestring import mark_safe
from lxml import html

from sendmail.settings import get_template_engine


def get_message_preview(instance):
    return f'{instance.message[:25]}...' if len(instance.message) > 25 else instance.message


get_message_preview.short_description = 'Message'


def render_placeholder_content(content):
    """Render placeholders content to replace {% inline_image %} tags with actual images. """
    engine = get_template_engine()
    template = engine.from_string(content)
    context = {'media': True, 'dry_run': False}
    return template.render(context)


def convert_media_urls_to_tags(content):
    """Convert media URLs back to {% inlined_image <url> %} tags using lxml."""
    tree = html.fromstring(content)

    for img in tree.xpath('//img'):
        src = img.get('src')
        if src and settings.MEDIA_URL in src:
            # Extract the media path after '/media/'
            media_path = src.split(settings.MEDIA_URL, 1)[1]
            # Replace src with the inlined_image template tag
            inline_img_tag = f"{{% inline_media_image '{pathlib.Path(settings.MEDIA_ROOT) / media_path}' %}}"
            img.set('src', inline_img_tag)

    html_str = html.tostring(tree, encoding='unicode', method='html')
    return mark_safe(html_str.replace('%20', ' '))


def get_language_name(code):
    return dict(settings.LANGUAGES).get(code, code)
