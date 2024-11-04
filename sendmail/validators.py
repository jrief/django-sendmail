from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.template import Template, TemplateDoesNotExist, TemplateSyntaxError
from django.utils.encoding import force_str


def validate_email_with_name(value):
    """
    Validate email address.

    Both "Recipient Name <email@example.com>" and "email@example.com" are valid.
    """
    value = force_str(value)

    recipient = value
    if '<' in value and '>' in value:
        start = value.find('<') + 1
        end = value.find('>')
        if start < end:
            recipient = value[start:end]

    validate_email(recipient)




def validate_template_syntax(source):
    """
    Basic Django Template syntax validation. This allows for robuster template
    authoring.
    """
    try:
        Template(source)
    except (TemplateSyntaxError, TemplateDoesNotExist) as err:
        raise ValidationError(str(err))
