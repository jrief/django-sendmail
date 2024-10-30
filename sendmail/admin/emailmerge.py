from django import forms
from django.conf import settings
from django.contrib import admin
from django.db import models
from django.forms import TextInput
from django.utils.text import Truncator
from django.utils.translation import gettext_lazy as _, override as translation_override

from sendmail.admin.placeholder import PlaceholderContentInline
from sendmail.models.emailmerge import EmailMergeModel, EmailMergeContentModel
from sendmail.settings import get_email_templates, get_default_language


class SubjectField(TextInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.attrs.update({'style': 'width: 610px;'})


class EmailMergeAdminForm(forms.ModelForm):
    change_form_template = 'admin/sendmail/emailtemplate/change_form.html'
    language = forms.ChoiceField(
        choices=settings.LANGUAGES,
        required=False,
        label=_('Language'),
        help_text=_('Render template in alternative language'),
    )
    base_file = forms.ChoiceField(
        choices=get_email_templates(),  # Set choices to the result of get_email_templates
        required=False,
        label=_('Base File'),
        help_text=_('Select the base email template file'),
    )

    class Meta:
        model = EmailMergeModel
        fields = ['name', 'description', 'base_file']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['language'].disabled = True


class EmailMergeContentForm(forms.ModelForm):
    language = forms.ChoiceField(
        choices=settings.LANGUAGES,
        required=False,
        label=_('Language'),
        help_text=_('Render template in alternative language'),
    )

    class Meta:
        model = EmailMergeContentModel
        fields = ['subject', 'content', 'language', 'extra_attachments']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['language'].disabled = True


class EmailMergeContentInline(admin.StackedInline):
    form = EmailMergeContentForm
    # formset = EmailTemplateAdminFormSet
    model = EmailMergeContentModel
    extra = 1
    fields = ('language', 'subject', 'content', 'extra_attachments')
    formfield_overrides = {models.CharField: {'widget': SubjectField}}

    filter_horizontal = ('extra_attachments',)

    def has_add_permission(self, request, obj):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EmailMergeModel)
class EmailMergeAdmin(admin.ModelAdmin):
    form = EmailMergeAdminForm
    list_display = ('name', 'created')
    search_fields = ('name', 'description', 'subject')
    fieldsets = [
        (None, {'fields': ('name', 'description', 'base_file', 'extra_recipients')}),
        # (_('Default Content'), {'fields': ('subject', 'content')}),
    ]
    inlines = [EmailMergeContentInline, PlaceholderContentInline]
    formfield_overrides = {models.CharField: {'widget': SubjectField}}

    filter_horizontal = ('extra_recipients',)

    def description_shortened(self, instance):
        return Truncator(instance.description.split('\n')[0]).chars(200)

    description_shortened.short_description = _('Description')
    description_shortened.admin_order_field = 'description'

    def languages_compact(self, instance):
        languages = [tt.language for tt in instance.translated_templates.order_by('language')]
        return ', '.join(languages)

    languages_compact.short_description = _('Languages')

    # def save_model(self, request, obj, form, change):
    #     obj.save()
    #     if not change:
    #         # the first time the object is saved, create a content object for the default language
    #         default_language = get_default_language()
    #         with translation_override(default_language):
    #             EmailMergeContentModel.objects.create(
    #                 subject=f'Subject, language: {default_language}',
    #                 content=f'Content, language: {default_language}',
    #                 emailmerge=obj,
    #                 language=default_language,
    #             )
