
from unittest import mock

import pytest
from django.core.files.images import ImageFile
from django.template import Context

from sendmail.template.tags.media_inline import inline_media_image
from sendmail.templatetags.sendmail import inline_image, placeholder


@pytest.mark.django_db
def test_dry_run():
    context = Context({'dry_run': True})
    result = inline_image(context, 'media/images/test.png')

    assert result == "{% inline_image 'media/images/test.png' %}"

    result = inline_media_image(context, 'images/test.png')
    assert result == "{% inline_media_image 'images/test.png' %}"


@pytest.mark.django_db
def test_media(settings):
    context = Context({'media': True})
    result = inline_media_image(context, str(settings.BASE_DIR / 'media/images/test.png'))
    assert result == "/media/images/test.png"


@pytest.mark.django_db
def test_absolute_path(settings):
    template = mock.Mock()
    template._attached_images = []
    context = Context({'dry_run': False})
    context.template = template
    path = settings.MEDIA_ROOT / 'logo.png'
    print(path)
    result = inline_media_image(context, path)
    assert result.startswith('cid:')
    assert len(template._attached_images) == 1
    assert template._attached_images[0].get_payload(decode=True) == open(path, 'rb').read()

    assert inline_media_image(context, 'images/test.png') == ''

    settings.DEBUG = True

    with pytest.raises(FileNotFoundError):
        inline_media_image(context, 'images/test.png')


@pytest.mark.django_db
def test_fileobj(settings):
    template = mock.Mock()
    template._attached_images = []
    context = Context({'dry_run': False})
    context.template = template
    path = str(settings.BASE_DIR / 'demoapp' / 'tests' / 'assets' / 'logo.png')
    file = ImageFile(open(path, 'rb'))
    result = inline_image(context, file)
    assert result.startswith('cid:')
    assert len(template._attached_images) == 1
    assert template._attached_images[0].get_payload(decode=True) == open(path, 'rb').read()

    path = str(settings.BASE_DIR / 'demoapp/static/images/logo.jpg')
    media_file = ImageFile(open(path, 'rb'))
    result = inline_media_image(context, media_file)
    assert result.startswith('cid:')
    assert len(template._attached_images) == 2
    assert template._attached_images[1].get_payload(decode=True) == open(path, 'rb').read()


def test_media_urls(settings):
    settings.MEDIA_ROOT = str(settings.BASE_DIR / 'demoapp' / 'tests' / 'assets')
    template = mock.Mock()
    template._attached_images = []
    context = Context({'dry_run': False})
    context.template = template
    filename = 'logo.png'
    abs_path = f"{settings.MEDIA_ROOT}/{filename}"
    result = inline_media_image(context, filename)
    assert result.startswith('cid:')
    assert len(template._attached_images) == 1
    assert template._attached_images[0].get_payload(decode=True) == open(abs_path, 'rb').read()


def test_placeholders():
    assert placeholder('test') == '{{test}}'


def test_static(settings):
    #settings.STATICFILES_DIRS = [str(settings.BASE_DIR / 'demoapp' / 'tests' / 'assets')]
    settings.DEBUG = True
    template = mock.Mock()
    template._attached_images = []
    context = Context({'dry_run': False})
    context.template = template
    filename = 'images/logo.jpg'
    abs_path = str(settings.BASE_DIR / 'demoapp/static/images/logo.jpg')
    result = inline_image(context, filename)
    assert result.startswith('cid:')
    assert len(template._attached_images) == 1
    assert template._attached_images[0].get_payload(decode=True) == open(abs_path, 'rb').read()

    with pytest.raises(FileNotFoundError):
        inline_image(context, 'invalid.png')

    with pytest.raises(IsADirectoryError):
        inline_image(context, 'images')


def test_staticfiles(settings, collectstatic):
    settings.DEBUG = False
    template = mock.Mock()
    template._attached_images = []
    context = Context({'dry_run': False})
    context.template = template

    filename = 'images/logo.jpg'
    result = inline_image(context, filename)
    assert result.startswith('cid:')
    assert len(template._attached_images) == 1

    assert inline_image(context, 'invalid') == ''


def test_track_link(settings):
    from sendmail.templatetags.sendmail import tracker_link

    media_link = 'images/logo.jpg'

    assert tracker_link(target_img=media_link, context={}) == ''

    assert tracker_link(target_img=media_link, context={'email_id': 5}) == 'https://example.com/sendmail/track/5/images/logo.jpg'
    # settings.MEDIA_ROOT = settings.BASE_DIR
    settings.DEBUG = True
    staticfiles_link = 'images/logo.jpg'

    assert tracker_link(target_img=staticfiles_link, context={'email_id': 5}) == 'https://example.com/sendmail/track/5/images/logo.jpg'

    with pytest.raises(FileNotFoundError):
            tracker_link(target_img='invalid.png', context={'email_id': 5, 'target_uri': 'https://google.com'})

    settings.DEBUG = False
    assert tracker_link(target_img='invalid.png', context={'email_id': 5, 'target_uri': 'https://google.com'}) == ''

def test_click_link():
    from sendmail.templatetags.sendmail import click_link
    from urllib.parse import quote

    target_uri = 'https://google.com'
    quoted = quote(target_uri)

    assert click_link(target_uri=target_uri, context={}) == ''

    assert click_link(target_uri=target_uri, context={'email_id': 5}) == f'https://example.com/sendmail/click/5/?target_uri={quoted}'



