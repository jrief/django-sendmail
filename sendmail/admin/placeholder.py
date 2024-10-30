from django.contrib import admin
from django.db.models import Case, When, Value, IntegerField

from sendmail.admin.emailmodel import EmailContentInlineFormset, EmailContentInlineForm
from sendmail.models.emailmerge import PlaceholderContent
from sendmail.settings import get_default_language


class PlaceholderContentInline(admin.TabularInline):
    model = PlaceholderContent
    formset = EmailContentInlineFormset
    form = EmailContentInlineForm
    extra = 0
    readonly_fields = ('get_language_display', 'placeholder_name')
    fields = ['content', 'get_language_display', 'placeholder_name', 'base_file']

    def get_language_display(self, obj):
        return obj.get_language_display()

    def get_formset(self, request, obj=None, **kwargs):
        self.parent_obj = obj
        formset = super().get_formset(request, obj, **kwargs)
        formset.request = request
        return formset

    def get_queryset(self, request, obj=None):
        queryset = super().get_queryset(request)
        default_language = get_default_language()

        if self.parent_obj and self.parent_obj.base_file:
            return queryset.filter(base_file=self.parent_obj.base_file).annotate(
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
