from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.db import models
from django.db.models import Case, IntegerField, Value, When
from django.forms import BaseInlineFormSet, TextInput
from django.db.models.fields.json import JSONField
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.text import Truncator
from django.utils.translation import gettext_lazy as _
from django.utils.translation import override as translation_override

from sendmail.admin.admin_utils import get_language_name
from sendmail.admin.placeholder import PlaceholderContentInline
from sendmail.mail import send
from sendmail.models.emailmerge import EmailMergeContentModel, EmailMergeModel
from sendmail.models.emailmodel import STATUS
from sendmail.settings import get_default_language, get_email_templates, get_languages_list

try:
    from jsoneditor.forms import JSONEditor
except ImportError:
    JSONEditor = None


class SubjectField(TextInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.attrs.update({'style': 'width: 610px;'})


class EmailMergeForm(forms.ModelForm):
    change_form_template = 'admin/sendmail/emailmergemodel/change_form.html'

    language = forms.ChoiceField(
        choices=settings.LANGUAGES,
        required=False,
        label=_("Language"),
        help_text=_("Render template in alternative language"),
    )
    template_file = forms.ChoiceField(
        choices=get_email_templates(),  # Set choices to the result of get_email_templates
        required=False,
        label=_("Base template file for email"),
        help_text=_('Select the base email template file'),
    )

    class Meta:
        model = EmailMergeModel
        fields = ['name', 'description', 'template_file']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['language'].readonly = True


class EmailMergeContentForm(forms.ModelForm):
    language = forms.ChoiceField(
        choices=settings.LANGUAGES,
        required=False,
        label=_('Language'),
        help_text=_('Render template in alternative language'),
    )

    def has_changed(self):
        return True

    class Meta:
        model = EmailMergeContentModel
        fields = ['subject', 'content', 'language', 'extra_attachments']

    def __init__(self, *args, available_languages=None, readonly_language=False, **kwargs):
        super().__init__(*args, **kwargs)
        # Set the filtered language choices
        if available_languages and not self.initial.get('language'):
            self.fields['language'].choices = available_languages

        if readonly_language:
            self.fields['language'].disabled = True

    def clean(self):
        cleaned_data = super().clean()
        if self.fields['language'].disabled:
            cleaned_data['language'] = get_default_language()

        return cleaned_data


class EmailMergeContentFormSet(BaseInlineFormSet):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)
        available_languages = [
            lang for lang in settings.LANGUAGES if lang[0] not in self.used_languages
        ]
        kwargs['available_languages'] = available_languages

        if index == 0:
            kwargs['readonly_language'] = True
        return kwargs


class EmailMergeContentInline(admin.StackedInline):
    form = EmailMergeContentForm
    model = EmailMergeContentModel
    fieldsets = [
        (None, {'fields': ['language', 'subject', 'content']}),
        (_("Extra Attachements"), {'fields': ['extra_attachments'], 'classes': ['collapse']}),
    ]
    formfield_overrides = {models.CharField: {'widget': SubjectField}}
    filter_horizontal = ('extra_attachments',)
    extra = 0


    def get_min_num(self, request, obj=None, **kwargs):
        if obj and not obj.translated_contents.filter(language=get_default_language()):
            return 1

        return 0

    def get_max_num(self, request, obj=None, **kwargs):
        return len(get_languages_list())

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        default_language = get_default_language()

        return queryset.annotate(is_default_lang=Case(
            When(language=default_language, then=Value(0)),
            default=Value(1),
            output_field=IntegerField()
        )
        ).order_by('is_default_lang')

    def get_formset(self, request, obj=None, **kwargs):
        # Get used languages if an instance exists
        used_languages = obj.get_available_languages() if obj else []
        kwargs['formset'] = EmailMergeContentFormSet
        formset = super().get_formset(request, obj, **kwargs)
        formset.used_languages = used_languages
        return formset


@admin.register(EmailMergeModel)
class EmailMergeAdmin(admin.ModelAdmin):
    form = EmailMergeForm
    list_display = ['name', 'created']
    search_fields = ['name', 'description', 'subject']
    fieldsets = [
        (None, {'fields': ['name', 'description', 'template_file']}),
        (_("Extra Recipients"), {'fields': ['extra_recipients'], 'classes': ['collapse']}),
        (_("Demo Context"), {'fields': ['demo_context'], 'classes': ['collapse']}),
    ]
    inlines = [EmailMergeContentInline, PlaceholderContentInline]
    formfield_overrides = {models.CharField: {'widget': SubjectField}, JSONField: {'widget': JSONEditor}}
    filter_horizontal = ['extra_recipients']

    class Media:
        css = {'all': ['admin/sendmail/css/emailmerge.css']}
        js = ['admin/sendmail/js/emailmerge.js']

    def send_email_view(self, request, obj):
        language = request.POST.get('email_language', None)
        admin_user = request.user
        admin_email = admin_user.email

        if not admin_email:
            messages.error(request, "Current admin user does not have an email address set.")
            return

        try:
            email = send(recipients=admin_email, emailmerge=obj, priority='now', language=language, context=obj.demo_context)
            if email.status == STATUS.sent:
                messages.success(request, "Email sent successfully to {admin_email}".format(admin_email=admin_email))
            else:
                messages.error(request, email.logs.last().message)

        except Exception as e:
            messages.error(request, f"An error has occurred: {e}")

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        messages_list = messages.get_messages(request)
        extra_context['messages'] = messages_list
        email = request.user.email
        if object_id:
            obj = EmailMergeModel.objects.get(pk=object_id)
            language_choices = [{'code': code, 'name': get_language_name(code)}
                                for code in obj.get_available_languages()]
        else:
            language_choices = []

        extra_context['show_send'] = True
        extra_context['show_reparse'] = True
        extra_context['language_options'] = language_choices
        extra_context['email'] = email
        return super().change_view(request, str(object_id), form_url=form_url, extra_context=extra_context)

    def response_change(self, request, obj):

        redirect_response = redirect(
                reverse(
                    'admin:%s_%s_change' % (self.model._meta.app_label, self.model._meta.model_name),
                    args=[obj.pk]
                ))

        if "_send_email" in request.POST:
            self.send_email_view(request, obj)
            return redirect_response

        if "_reparse" in request.POST:
            obj.reparse_context()
            return redirect_response



        return super().response_change(request, obj)

    def description_shortened(self, instance):
        return Truncator(instance.description.split('\n')[0]).chars(200)

    description_shortened.short_description = _('Description')
    description_shortened.admin_order_field = 'description'

    def languages_compact(self, instance):
        languages = [tt.language for tt in instance.translated_templates.order_by('language')]
        return ', '.join(languages)

    languages_compact.short_description = _('Languages')

    def save_model(self, request, obj, form, change):
        obj.save()
        if not change:
            # the first time the object is saved, create a content object for the default language
            default_language = get_default_language()
            with translation_override(default_language):
                EmailMergeContentModel.objects.create(
                    subject=f'Subject, language: {default_language}',
                    content=f'Content, language: {default_language}',
                    emailmerge=obj,
                    language=default_language,
                )

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)

        obj = form.instance

        if obj and change:
            obj.remove_extra_placeholders()
