import pytest

from sendmail.models import PlaceholderContent
from sendmail.parser import extract_variable_names, get_ckeditor_variables, process_template


def test_parse_base_template():
    placeholders = process_template('test/base.html')
    assert list(placeholders) == ['content']


def test_parse_extend_base_template():
    placeholders = process_template('test/extended_base.html')
    assert list(placeholders) == ['content']


def test_parse_extend_after_template():
    placeholders = process_template('test/extend_base_after.html')
    assert list(placeholders) == ['content', 'after']


def test_parse_extend_before_template():
    placeholders = process_template('test/extend_base_before.html')
    assert list(placeholders) == ['before', 'content']


def test_parse_include_other_template():
    placeholders = process_template('test/include_other.html')
    assert list(placeholders) == ['content', 'other']


def test_parse_extend_include_other_template():
    placeholders = process_template('test/extend_include_other.html')
    assert list(placeholders) == ['content', 'other', 'between', 'other']


def test_parse():
    assert sorted(process_template('test/parse_test.html')) == sorted(
        ['place1', 'place_true', 'place_false', 'place_loop',
         'inner', 'inner_true', 'place_block'])


def test_extract_vars():
    assert (extract_variable_names('test/parse_test.html') ==
            {'var1': '',
             'var_true': '',
             'var_false': '',
             'list': [
                 {
                     'var_loop': ''
                 }
             ],
             'var_inner': '',
             'var_inner_true': '',
             'var_block': ''})


@pytest.mark.django_db
def test_ckeditor_vars(template):
    placeholder1 = PlaceholderContent.objects.get(placeholder_name='test1', language='en')
    placeholder2 = PlaceholderContent.objects.get(placeholder_name='test2', language='en')

    placeholder1.content = 'This is a #var1#'
    placeholder1.save()

    placeholder2.content = 'This is a #var2# and #var1# and #new.var1#'
    placeholder2.save()

    assert sorted(get_ckeditor_variables(template)) == sorted(['var1', 'var2', 'new.var1'])
