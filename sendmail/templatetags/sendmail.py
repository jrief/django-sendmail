import uuid
from email.mime.image import MIMEImage
from pathlib import Path

from django import template
from django.conf import settings
from urllib.parse import quote
from django.contrib.staticfiles.finders import find
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.files.images import ImageFile
from django.urls import reverse
from django.utils.html import SafeString

from sendmail.settings import get_tracking_enabled, get_tracking_domain

register = template.Library()


@register.simple_tag(takes_context=True)
def inline_image(context, file):
    if context.get('dry_run'):
        return SafeString(f"{{% inline_image '{file}' %}}")

    assert hasattr(
        context.template, '_attached_images'
    ), "You must use template engine 'sendmail' when rendering images using templatetag 'inline_image'."
    if isinstance(file, ImageFile):
        fileobj = file.open('rb')
    else:
        if settings.DEBUG:
            path = find(file)
            fullpath = Path(path) if path else None
            if not fullpath:
                raise FileNotFoundError(f"No such file in static: {file}")
            if not fullpath.is_file():
                raise IsADirectoryError(f"File {file} is not a file")
            fileobj = fullpath.open('rb')
        else:
            if staticfiles_storage.exists(file):
                fileobj = staticfiles_storage.open(file)
            else:
                return ''
    raw_data = fileobj.read()
    image = MIMEImage(raw_data)
    fileobj.close()
    cid = uuid.uuid4().hex
    image.add_header('Content-Disposition', 'inline', filename=cid)
    image.add_header('Content-ID', f'<{cid}>')
    context.template._attached_images.append(image)
    return f'cid:{cid}'


@register.simple_tag
def placeholder(name: str) -> str:
    return f"{{{{{name}}}}}"

if get_tracking_enabled():

    def build_url(path):
        return "{}{}".format(get_tracking_domain(), path)

    @register.simple_tag(takes_context=True)
    def tracker(context, target_img) -> str:
        if not (email_id := context.get('email_id')):
            return ''


        url = reverse('sendmail:track', args=[email_id, target_img])

        return build_url(url)

    @register.simple_tag(takes_context=True)
    def click_link(context, target_uri):

        if not (email_id := context.get('email_id')):
            return ''

        url = reverse('sendmail:click', args=[email_id])
        return f"{build_url(url)}?target_uri={quote(target_uri)}"




