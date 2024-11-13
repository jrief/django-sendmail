import uuid
from email.mime.image import MIMEImage
from pathlib import Path

from django import template
from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage
from django.contrib.staticfiles.finders import find
from django.core.files.images import ImageFile
from django.core.files.storage import default_storage
from django.utils.html import SafeString

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


@register.simple_tag(takes_context=True)
def inline_media_image(context, file):
    if context.get('dry_run'):
        return SafeString(f"{{% inline_media_image '{file}' %}}")

    if context.get('media'):
        file_name = file.split(settings.MEDIA_URL[1:])[-1]
        return f"{settings.MEDIA_URL}{file_name}"

    assert hasattr(
        context.template, '_attached_images'
    ), "You must use template engine 'sendmail' when rendering images using templatetag 'inline_image'."
    if isinstance(file, ImageFile):
        fileobj = file
    else:
        if default_storage.exists(file):
            fileobj = default_storage.open(file)
        else:
            if settings.DEBUG:
                raise FileNotFoundError(f"No such file in media: {file}")
            else:
                return ''
    raw_data = fileobj.read()
    fileobj.close()
    image = MIMEImage(raw_data)
    cid = uuid.uuid4().hex
    image.add_header('Content-Disposition', 'inline', filename=cid)
    image.add_header('Content-ID', f'<{cid}>')
    context.template._attached_images.append(image)
    return f'cid:{cid}'


@register.simple_tag
def placeholder(name: str) -> str:
    return f"{{{{{name}}}}}"