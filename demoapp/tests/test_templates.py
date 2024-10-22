import pytest
from sendmail.models import EmailMergeModel, PlaceholderContent, EmailAddress, EmailMergeContentModel


@pytest.fixture
def test_template():
    template = EmailMergeModel.objects.create(
        base_file='test/test.html',
        name='test_name',
        description='test_description',
        # subject='test_subject',
        # content='test_content',
        # language='en',
    )

    en_content = template.translated_contents.get(language='en')
    en_content.subject = 'test_subject'
    en_content.content = 'test_content'
    en_content.save()
    return template


@pytest.mark.django_db
def test_creation(test_template):
    assert EmailMergeContentModel.objects.count() == 2
    assert EmailMergeModel.objects.count() == 1

    main = EmailMergeModel.objects.first()
    assert main.translated_contents.count() == 2
    en_content = main.translated_contents.get(language='en')

    assert main.name == 'test_name'
    assert en_content.subject == 'test_subject'
    assert en_content.content == 'test_content'

    de_content = main.translated_contents.get(language='de')

    assert de_content.subject == 'Subject, language: de'

    assert de_content.content == 'Content, language: de'

    placeholders_base = PlaceholderContent.objects.values_list('base_file', flat=True)

    assert len(placeholders_base) == 4

    assert all([place == 'test/test.html' for place in placeholders_base])

    placeholders = PlaceholderContent.objects.values_list('placeholder_name', 'language')

    assert sorted(placeholders) == sorted([('test1', 'en'), ('test2', 'en'), ('test1', 'de'), ('test2', 'de')])

    assert PlaceholderContent.objects.get(placeholder_name='test1', language='en').content == ('Placeholder: test1, '
                                                                                               'Language: en')


@pytest.mark.django_db
def test_render_template(test_template):
    rendered = test_template.render_email_template(language='en')
    clean = rendered.replace('\n', '').replace('\t', '').replace('\r', '').strip()
    html_string = (' {% load sendmail %}'
                   ' <!DOCTYPE html><html lang="en">'
                   '<head>'
                   '    <meta charset="UTF-8">'
                   '    <title>Test</title>'
                   '</head>'
                   '<body>'
                   '    Placeholder: test1, Language: en'
                   '    Placeholder: test2, Language: en'
                   '</body>'
                   '</html>').strip()
    assert clean == html_string

    template_context = EmailMergeModel.objects.create(
        base_file='test/context_test.html',
        name='test',
        description='test_description',
    )

    en_content = template_context.translated_contents.get(language='en')
    en_content.subject = 'test_subject'
    en_content.content = 'test_content'
    en_content.save()

    rendered = template_context.render_email_template(context_dict={'test_var': 'VALUE'},
                                                      recipient=EmailAddress.objects.create(
                                                          email='test@email.com',
                                                          first_name='Name',
                                                          last_name='Surname',
                                                      ),
                                                      language='en')
    clean = rendered.replace('\n', '').replace('\t', '').replace('\r', '').strip()

    html_string = (' {% load sendmail %}'
                   ' <!DOCTYPE html><html lang="en">'
                   '<head>'
                   '    <meta charset="UTF-8">'
                   '    <title>Test</title>'
                   '</head>'
                   '<body>'
                   '    Name'
                   '    Surname'
                   '    Placeholder: test1, Language: en'
                   '    Placeholder: test2, Language: en'
                   '    VALUE'
                   '</body>'
                   '</html>').strip()

    assert clean == html_string
