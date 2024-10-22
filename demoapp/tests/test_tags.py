import pathlib

import pytest
from django.core.files.images import ImageFile
import re
from django.template import Context, Template
from sendmail.templatetags.sendmail import inline_image, placeholder
from unittest import mock


@pytest.mark.django_db
def test_dry_run():
    context = Context({'dry_run': True})
    result = inline_image(context, 'media/images/test.png')

    assert result == "{% inline_image 'media/images/test.png' %}"


@pytest.mark.django_db
def test_media(settings):
    context = Context({'media': True})
    result = inline_image(context, str(settings.BASE_DIR / 'media/images/test.png'))
    assert result == "/media/images/test.png"



@pytest.mark.django_db
def test_absolute_path(settings):
    template = mock.Mock()
    template._attached_images = []
    context = Context({'dry_run': False})
    context.template = template
    path = str(settings.BASE_DIR / 'demoapp' / 'tests' / 'assets' / 'logo.png')
    print(path)
    result = inline_image(context, path)
    assert result.startswith('cid:')
    assert len(template._attached_images) == 1
    assert template._attached_images[0].get_payload(decode=True) == open(path, 'rb').read()


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


def test_media_urls(settings):
    settings.MEDIA_ROOT = str(settings.BASE_DIR / 'demoapp' / 'tests' / 'assets')
    template = mock.Mock()
    template._attached_images = []
    context = Context({'dry_run': False})
    context.template = template
    filename = 'logo.png'
    abs_path = f"{settings.MEDIA_ROOT}/{filename}"
    result = inline_image(context, filename)
    assert result.startswith('cid:')
    assert len(template._attached_images) == 1
    assert template._attached_images[0].get_payload(decode=True) == open(abs_path, 'rb').read()


def test_placeholders():
    assert placeholder('test') == '{{test}}'


def test_static(settings):
    settings.STATICFILES_DIRS = [str(settings.BASE_DIR / 'demoapp' / 'tests' / 'assets')]
    template = mock.Mock()
    template._attached_images = []
    context = Context({'dry_run': False})
    context.template = template
    filename = 'logo.png'
    abs_path = str(settings.BASE_DIR / 'demoapp' / 'tests' / 'assets' / filename)
    result = inline_image(context, pathlib.Path('assets') / filename)
    assert result.startswith('cid:')
    assert len(template._attached_images) == 1
    assert template._attached_images[0].get_payload(decode=True) == open(abs_path, 'rb').read()

    assert inline_image(context, 'invalid.png') == ''

    settings.DEBUG = True

    with pytest.raises(FileNotFoundError):
        inline_image(context, 'invalid.png')
