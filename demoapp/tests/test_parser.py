import pytest

from sendmail.models import PlaceholderContent
from sendmail.parser import process_template, extract_variable_names, get_ckeditor_variables


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
