import uuid
from email.mime.image import MIMEImage
from urllib.parse import quote

from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.files.images import ImageFile
from django.core.files.storage import default_storage
from django.template import Library, Node
from django.urls import reverse
from django.utils.html import SafeString

from sendmail.settings import get_tracking_domain, get_tracking_enabled
from sendmail.utils import get_path_from_static

register = Library()


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
            fullpath = get_path_from_static(file)
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


class PlaceholderNode(Node):
    def __init__(self, name):
        self.name = name

    def render(self, context):
        return context.get(self.name, '')


@register.tag
def placeholder(parser, token):
    _, name = token.split_contents()
    if not (name.startswith('\'') and name.endswith('\'') or name.startswith('"') and name.endswith('"')):
        raise ValueError("Placeholder name must be quoted.")
    return PlaceholderNode(name[1:-1])


if get_tracking_enabled():

    def build_url(path):
        return "{}{}".format(get_tracking_domain(), path)

    @register.simple_tag(takes_context=True)
    def tracker_link(context, target_img) -> str:
        if not (email_id := context.get('email_id')):
            return ''

        if not default_storage.exists(target_img):
            if settings.DEBUG:
                get_path_from_static(target_img)
            elif not staticfiles_storage.exists(target_img):
                return ''

        url = reverse('sendmail:track', args=[email_id, target_img])

        return build_url(url)

    @register.simple_tag(takes_context=True)
    def click_link(context, target_uri):

        if not (email_id := context.get('email_id')):
            return ''

        url = reverse('sendmail:click', args=[email_id])
        return f"{build_url(url)}?target_uri={quote(target_uri)}"
