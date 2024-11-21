from ckeditor_uploader.fields import RichTextUploadingField
from django.conf import settings
from django.db import models
from django.template import loader
from django.utils.translation import gettext_lazy as _

from sendmail import cache
from sendmail.cache_utils import get_placeholder_names, get_placeholders
from sendmail.logutils import setup_loghandlers
from sendmail.sanitizer import clean_html
from sendmail.settings import get_email_address_setting, get_template_engine
from sendmail.validators import validate_template_syntax
from sendmail.parser import get_variables_names, extract_variable_names, get_ckeditor_variables

logger = setup_loghandlers('INFO')


class EmailMergeModel(models.Model):
    """
    Model to hold template information from db
    """

    name = models.CharField(
        verbose_name=_("Name"),
        max_length=255,
        help_text=_("e.g: 'welcome_email'"),
        unique=True,
    )
    description = models.TextField(
        verbose_name=_("Description"),
        blank=True,
        help_text=_("Description of this mail merge object."),
    )
    template_file = models.CharField(
        max_length=255,
        verbose_name=_("Template file"),
        # choices=get_email_templates(),  # Set choices to the result of get_email_templates
    )
    created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    extra_recipients = models.ManyToManyField(
        get_email_address_setting(),
        blank=True,
        help_text='extra bcc recipients',
    )

    class Meta:
        app_label = 'sendmail'
        verbose_name = _('Email Merge Object')
        verbose_name_plural = _('Email Merge Objects')
        ordering = ['name']

    def __str__(self):
        return self.name

    def render_email_template(self, language='', recipient=None, context_dict=None):
        """
        Function to render an email template. Takes an EmailAddress object and a dictionary of context variables.
        """
        if not language:
            raise
        if not context_dict:
            context_dict = {}

        engine = get_template_engine()
        context = {'recipient': recipient, 'dry_run': True, **context_dict} \
            if recipient else {'dry_run': True, **context_dict}

        django_template_first_pass = loader.get_template(self.template_file, using='sendmail')

        # Replace all {% placeholder <name> %} to {{ name }}
        first_pass_content = django_template_first_pass.render(context)

        placeholders = get_placeholders(self, language=language)
        context_data = {placeholder.placeholder_name: clean_html(placeholder.content) for placeholder in placeholders}
        context_data = {**context_data, 'dry_run': True}

        # Replaces placeholders with actual values
        django_template_second_pass = engine.from_string("{% load sendmail %}" + first_pass_content)
        final_content = django_template_second_pass.render(context_data)

        final_content = f"{{% load sendmail %}}\n {final_content}"

        return final_content

    def get_available_languages(self):
        return list(self.translated_contents.values_list('language', flat=True))

    def remove_extra_placeholders(self):
        available_languages = self.get_available_languages()
        self.contents.exclude(language__in=available_languages).delete()

    def save(self, *args, **kwargs):
        template = super().save(*args, **kwargs)
        cache.delete(self.name, category='template')

        return template


class EmailMergeContentModel(models.Model):
    """
    Model to hold EmailMerge data exclusive for every language.
    """
    emailmerge = models.ForeignKey(
        EmailMergeModel,
        related_name='translated_contents',
        on_delete=models.CASCADE,
    )
    language = models.CharField(max_length=12)
    subject = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Subject'),
        validators=[validate_template_syntax]
    )
    content = models.TextField(
        blank=True,
        verbose_name=_('Content'),
        validators=[validate_template_syntax],
    )
    extra_attachments = models.ManyToManyField(
        'Attachment',
        related_name='extra_attachments',
        verbose_name=_('Extra Attachments'),
        blank=True,
    )

    def __str__(self):
        return f"{self.emailmerge.name}: {self.language}"

    def save(self, *args, **kwargs):
        """
        On save of EmailMergeContent parses the template file and create a set of placeholders.
        """
        super().save(*args, **kwargs)

        cache_key = f'{self.emailmerge.name}:{self.language}:{self.emailmerge.template_file}'
        cache.delete(cache_key, category='placeholders')

        emailmerge = self.emailmerge

        placeholders_names = get_placeholder_names(emailmerge)
        existing_placeholders = set(
            emailmerge.contents.
            filter(used_template_file=emailmerge.template_file).
            filter(language=self.language).values_list('placeholder_name', flat=True)
        )

        placeholder_objs = []
        for placeholder_name in (placeholders_names - existing_placeholders):
            placeholder_objs.append(
                PlaceholderContent(
                    placeholder_name=placeholder_name,
                    language=self.language,
                    used_template_file=emailmerge.template_file,
                    emailmerge=emailmerge,
                    content=f"Placeholder: {placeholder_name}, Language: {self.language}",
                )
            )
        PlaceholderContent.objects.bulk_create(placeholder_objs)

        return self

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['emailmerge', 'language'],
                name='unique_content'
            ),
        ]
        app_label = 'sendmail'
        verbose_name = _('Email Template Content')
        verbose_name_plural = _('Email Template Contents')


class PlaceholderContent(models.Model):
    """
    Model to store user added placeholders data.
    """

    emailmerge = models.ForeignKey(
        EmailMergeModel,
        on_delete=models.CASCADE,
        related_name='contents',
    )
    language = models.CharField(
        max_length=12,
        default='',
        blank=True,
        choices=[]
    )
    placeholder_name = models.CharField(
        verbose_name=_("Placeholder name"),
        max_length=63,
    )
    content = RichTextUploadingField(
        verbose_name=_("Content"),
        default='',
    )
    used_template_file = models.CharField(
        verbose_name="Template File",
        max_length=255,
        help_text="Template file used when creating this placeholder.",
    )

    def get_language_display(self):
        return dict(settings.LANGUAGES).get(self.language, self.language)

    class Meta:
        app_label = 'sendmail'
        constraints = [
            models.UniqueConstraint(
                fields=['emailmerge', 'placeholder_name', 'language', 'used_template_file'],
                name='unique_placeholder',
            ),
        ]

    def __str__(self):
        return f"{self.placeholder_name} ({self.get_language_display()})"

    def save(self, *args, **kwargs):
        cache_key = f'{self.emailmerge.name}:{self.language}:{self.used_template_file}'
        cache.delete(cache_key, category='placeholders')
        return super().save(*args, **kwargs)
