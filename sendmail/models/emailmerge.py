from ckeditor_uploader.fields import RichTextUploadingField
from django.conf import settings
from django.db import models
from django.template import loader
from django.utils.translation import gettext_lazy as _

from sendmail import cache
from sendmail.cache_utils import get_placeholders
from sendmail.logutils import setup_loghandlers
from sendmail.models.emailaddress import EmailAddress
from sendmail.parser import process_template
from sendmail.sanitizer import clean_html
from sendmail.settings import get_languages_list, get_template_engine
from sendmail.validators import validate_template_syntax

logger = setup_loghandlers('INFO')


class EmailMergeModel(models.Model):
    """
    Model to hold template information from db
    """

    base_file = models.CharField(
        max_length=255,
        verbose_name=_('File name'),
        # choices=get_email_templates(),  # Set choices to the result of get_email_templates
    )
    name = models.CharField(_('Name'), max_length=255, help_text=_("e.g: 'welcome_email'"), unique=True)
    description = models.TextField(_('Description'), blank=True, help_text=_('Description of this template.'))
    created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    extra_recipients = models.ManyToManyField(
        EmailAddress,
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
        Function to render an email template. Takes an EmailAddress object.
        """
        if not language:
            raise
        if not context_dict:
            context_dict = {}

        engine = get_template_engine()
        context = {'recipient': recipient, 'dry_run': True, **context_dict} \
            if recipient else {'dry_run': True, **context_dict}

        django_template_first_pass = loader.get_template(self.base_file, using='sendmail')

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

    def save(self, *args, **kwargs):
        template = super().save(*args, **kwargs)
        cache.delete(self.name)

        # placeholder_names = process_template(self.base_file)
        #
        # existing_placeholders = set(
        #     self.contents.filter(base_file=self.base_file).values_list('placeholder_name',
        #                                                                'language'))
        #
        # placeholder_objs = []
        # for placeholder_name in placeholder_names:
        #     for lang in get_languages_list():
        #         if (placeholder_name, lang) not in existing_placeholders:
        #             placeholder_objs.append(PlaceholderContent(placeholder_name=placeholder_name,
        #                                                        language=lang,
        #                                                        base_file=self.base_file,
        #                                                        emailmerge=self,
        #                                                        content=f"Placeholder: {placeholder_name}, "
        #                                                                f"Language: {lang}", ), )
        #
        # PlaceholderContent.objects.bulk_create(placeholder_objs)

        return template


class EmailMergeContentModel(models.Model):
    emailmerge = models.ForeignKey(EmailMergeModel,
                                   related_name='translated_contents',
                                   on_delete=models.CASCADE)
    language = models.CharField(max_length=12)
    subject = models.CharField(max_length=255,
                               blank=True,
                               verbose_name=_('Subject'),
                               validators=[validate_template_syntax]
                               )
    content = models.TextField(blank=True,
                               verbose_name=_('Content'),
                               validators=[validate_template_syntax])
    extra_attachments = models.ManyToManyField('Attachment',
                                               related_name='extra_attachments',
                                               verbose_name=_('Extra Attachments'),
                                               blank=True,
                                               )

    def __str__(self):
        return f"{self.emailmerge.name}: {self.language}"

    def save(self, *args, **kwargs):
        # cache.delete('placeholders %s:%s:%s' % (self.emailmerge.name, self.language, self.base_file))
        self.full_clean()
        super().save(*args, **kwargs)

        template = self.emailmerge

        placeholders_names = set(process_template(template.base_file))

        existing_placeholders = set(template.contents.
                                    filter(base_file=template.base_file).
                                    filter(language=self.language).
                                    values_list('placeholder_name', flat=True))

        placeholder_objs = []

        for placeholder_name in (placeholders_names - existing_placeholders):
            placeholder_objs.append(PlaceholderContent(placeholder_name=placeholder_name,
                                                       language=self.language,
                                                       base_file=template.base_file,
                                                       emailmerge=template,
                                                       content=f"Placeholder: {placeholder_name}, "
                                                               f"Language: {self.language}", ), )

        PlaceholderContent.objects.bulk_create(placeholder_objs)

        return self

    def delete(self, *args, **kwargs):
        deleted = (PlaceholderContent.objects.
                   filter(emailmerge=self.emailmerge).
                   filter(language=self.language).
                   delete())
        return super().delete(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['emailmerge', 'language'],
                                    name='unique_content'),
        ]
        app_label = 'sendmail'
        verbose_name = _('Email Template Content')
        verbose_name_plural = _('Email Template Contents')


class PlaceholderContent(models.Model):
    emailmerge = models.ForeignKey(EmailMergeModel,
                                   on_delete=models.CASCADE,
                                   related_name='contents', )
    language = models.CharField(
        max_length=12,
        default='',
        blank=True,
        choices=settings.LANGUAGES,
    )
    placeholder_name = models.CharField(_('Placeholder name'),
                                        max_length=63, )
    content = RichTextUploadingField(_('Content'), default='')

    base_file = models.CharField(max_length=255, verbose_name=_('File name'))

    class Meta:
        app_label = 'sendmail'
        constraints = [
            models.UniqueConstraint(fields=['emailmerge', 'placeholder_name', 'language', 'base_file'],
                                    name='unique_placeholder'),
        ]

    def save(self, *args, **kwargs):
        cache.delete('placeholders %s:%s:%s' % (self.emailmerge.name, self.language, self.base_file))
        return super().save(*args, **kwargs)
