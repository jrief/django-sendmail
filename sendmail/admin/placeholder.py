from ckeditor_uploader.fields import RichTextUploadingFormField
from django import forms
from django.contrib import admin
from django.db.models import Case, IntegerField, Value, When
from django.forms import HiddenInput

from sendmail.admin.admin_utils import convert_media_urls_to_tags, render_placeholder_content
from sendmail.models.emailmerge import PlaceholderContent
from sendmail.settings import get_default_language


class CKEditorFormField(RichTextUploadingFormField):
    def widget(self, **kwargs):
        return super().widget(template_name='admin/ckeditor/widget.html', **kwargs)


class PlaceholderContentInlineForm(forms.ModelForm):
    content = CKEditorFormField()

    class Meta:
        model = PlaceholderContent
        fields = ['language', 'placeholder_name', 'content', 'used_template_file']
        widgets = {
            'used_template_file': HiddenInput(),  # TODO: never trust user input, this should be done during save()
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if 'content' in self.initial:
            self.initial['content'] = render_placeholder_content(self.initial['content'])

    def save(self, commit=True):
        self.instance.content = convert_media_urls_to_tags(self.cleaned_data['content'])

        return super().save(commit=commit)


class PlaceholderContentInline(admin.TabularInline):
    model = PlaceholderContent
    form = PlaceholderContentInlineForm
    extra = 0
    fields = ['content', 'used_template_file']

    def get_formset(self, request, obj=None, **kwargs):
        self.parent_obj = obj
        formset = super().get_formset(request, obj, **kwargs)
        formset.request = request
        return formset

    def get_queryset(self, request, obj=None):
        queryset = super().get_queryset(request)
        default_language = get_default_language()

        if self.parent_obj and self.parent_obj.template_file:
            return queryset.filter(used_template_file=self.parent_obj.template_file).annotate(
                is_default_lang=Case(
                    When(language=default_language, then=Value(0)),
                    default=Value(1),
                    output_field=IntegerField()
                )
            ).order_by('is_default_lang', 'language')

        return queryset

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
