import pytest
from sendmail.admin import get_message_preview, render_placeholder_content, convert_media_urls_to_tags
from dataclasses import dataclass


def test_message_preview():
    @dataclass
    class TestClass:
        message: str

    obj = TestClass(message='a' * 30)
    assert get_message_preview(obj) == 'a' * 25 + '...'

    obj = TestClass(message='a' * 20)
    assert get_message_preview(obj) == 'a' * 20


def test_render_placeholder_content(settings):
    rendered = render_placeholder_content(
        f"<img src='{{% inline_image '{settings.BASE_DIR}/media/images/logo.png' %}}'>",
    )

    assert rendered == "<img src='/media/images/logo.png'>"


def test_media_to_tags(settings):
    converted = convert_media_urls_to_tags("<img src='https://example.com/media/images/logo.png'")

    assert converted == f"<img src=\"{{% inline_image '{settings.MEDIA_ROOT}/images/logo.png' %}}\">"
