import uuid
from email.mime.image import MIMEImage

from django import template
from django.conf import settings
from django.core.files.images import ImageFile
from django.core.files.storage import default_storage
from django.utils.safestring import SafeString

register = template.Library()


@register.simple_tag(takes_context=True)
def inline_media_image(context, file):
    if context.get('dry_run'):
        return SafeString(f"{{% inline_media_image '{file}' %}}")

    if context.get('media'):
        file_name = file.split(settings.MEDIA_URL[1:])[-1]
        return f"{settings.MEDIA_URL}{file_name}"

    assert hasattr(
        context.template, '_attached_images'
    ), "You must use template engine 'sendmail' when rendering images using templatetag 'media_inline_image'."
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
