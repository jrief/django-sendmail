from ckeditor_uploader.fields import RichTextUploadingField
from django.conf import settings
from django.db import models
from django.template import loader
from django.utils.translation import gettext_lazy as _

from sendmail import cache
from sendmail.cache_utils import get_placeholder_names, get_placeholders
from sendmail.logutils import setup_loghandlers
from sendmail.sanitizer import clean_html
from sendmail.settings import get_email_address_setting
from sendmail.validators import validate_template_syntax
from sendmail.parser import extract_variable_names, get_ckeditor_variables

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
    demo_context = models.JSONField(
        blank=True,
        null=True,
        verbose_name=_("Demo context"),
        help_text=_("Example context for previewing the email template."),
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
        Renders an email template based on the specified language, recipient,
        and context. The rendering involves a two-pass processing of the template
        to replace placeholders with their actual values and ensure the content
        is cleaned and appropriately formatted before being returned. This method
        requires specifying a language and can optionally take a recipient and
        context dictionary to personalize the email content.

        Parameters:
            language (str): Specifies the language for rendering the email template.
            recipient: The recipient of the email, which can be used for personalized content.
            context_dict: Optional dictionary containing additional context for rendering.

        Returns:
            str: The final rendered email content with placeholders replaced by actual
            values.

        Raises:
            ValueError: If the language parameter is not specified.
        """
        if not language:
            raise ValueError("Language is required to render email template.")

        if not context_dict:
            context_dict = {}

        # Get placeholders from cache or db
        placeholders = get_placeholders(self, language=language)
        placeholders_dict = {placeholder.placeholder_name: clean_html(placeholder.content) for placeholder in placeholders}

        # Create a context
        context = {'recipient': recipient, 'dry_run': True, **context_dict, **placeholders_dict} \
            if recipient else {'dry_run': True, **context_dict, **placeholders_dict}

        django_template_first_pass = loader.get_template(self.template_file, using='sendmail')

        rendered = django_template_first_pass.render(context)

        final_content = f"{{% load sendmail %}}\n {rendered}"

        return final_content

    def construct_default_json(self):
        """
        Constructs a default JSON-like dictionary containing template variables.

        The method generates a dictionary of variables, with the variable names
        as keys and empty strings as values. It differentiates between scenarios
        where an email merge template is used and where custom text variables
        need to be extracted. In the case of an email merge, it combines variables
        from the template file and additional variables from the CKEditor. When an
        email merge isn't used, the method extracts custom variables from various
        text sources such as 'subject', 'message', and 'html_message', filtering
        out variables that start with 'recipient'.

        Returns:
            dict: A dictionary with variable names as keys and empty strings as values.

        """
        template_vars = extract_variable_names(self.template_file)
        if self.pk:
            ckeditor_vars = get_ckeditor_variables(self)
        else:
            ckeditor_vars = []
        vars_dict = {**template_vars, **{var: '' for var in ckeditor_vars}}
        return vars_dict

    def get_available_languages(self):
        return list(self.translated_contents.values_list('language', flat=True))

    def remove_extra_placeholders(self):
        available_languages = self.get_available_languages()
        self.contents.exclude(language__in=available_languages).delete()

    def save(self, *args, **kwargs):
        cache.delete(self.name, category='template')

        if self.pk:
            old_instance = EmailMergeModel.objects.get(pk=self.pk)
            if old_instance.template_file != self.template_file:
                # If you change template_file all the context should be erased
                self.demo_context = None

        if not self.demo_context:
            self.demo_context = self.construct_default_json()


        template = super().save(*args, **kwargs)

        return template

    def reparse_context(self):
        self.demo_context = self.construct_default_json()
        self.save()


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
