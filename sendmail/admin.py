import pathlib
import re
from lxml import html
from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.core.mail.message import SafeMIMEText
from django.db import models
from django.forms import BaseInlineFormSet
from django.forms.widgets import TextInput, HiddenInput
from django.http.response import HttpResponse, HttpResponseNotFound, HttpResponseRedirect
from django.urls import re_path, reverse
from django.utils.html import format_html
from django.utils.text import Truncator
from django.utils.translation import gettext_lazy as _
from django.utils.safestring import mark_safe
from django.db.models import Case, When, Value, IntegerField

from .models import STATUS, Attachment, EmailModel, EmailMergeModel, Log, EmailAddress, PlaceholderContent, \
    EmailMergeContentModel, Recipient
from .sanitizer import clean_html
from .settings import get_default_language, get_template_engine, get_base_files


def get_message_preview(instance):
    return f'{instance.message[:25]}...' if len(instance.message) > 25 else instance.message


get_message_preview.short_description = 'Message'


def render_placeholder_content(content):
    """Render placeholders content to replace {% inline_image %} tags with actual images. """
    engine = get_template_engine()
    template = engine.from_string(f"{{% load sendmail %}}{content}")
    context = {'media': True, 'dry_run': False}
    return template.render(context)


def convert_media_urls_to_tags(content):
    """Convert media URLs back to {% inlined_image <url> %} tags using lxml."""
    tree = html.fromstring(content)

    for img in tree.xpath('//img'):
        src = img.get('src')
        if src and settings.MEDIA_URL in src:
            # Extract the media path after '/media/'
            media_path = src.split(settings.MEDIA_URL, 1)[1]
            # Replace src with the inlined_image template tag
            inline_img_tag = f"{{% inline_image '{pathlib.Path(settings.MEDIA_ROOT) / media_path}' %}}"
            img.set('src', inline_img_tag)

    html_str = html.tostring(tree, encoding='unicode', method='html')
    return mark_safe(html_str.replace('%20', ' '))


class AttachmentInline(admin.StackedInline):
    model = Attachment.emails.through
    extra = 0
    autocomplete_fields = ['attachment']

    def get_formset(self, request, obj=None, **kwargs):
        self.parent_obj = obj
        return super().get_formset(request, obj, **kwargs)

    def get_queryset(self, request):
        """
        Exclude inlined attachments from queryset, because they usually have meaningless names and
        are displayed anyway.
        """
        queryset = super().get_queryset(request)
        if self.parent_obj:
            queryset = queryset.filter(emailmodel=self.parent_obj)

        inlined_attachments = [
            a.id
            for a in queryset
            if isinstance(a.attachment.headers, dict)
               and a.attachment.headers.get('Content-Disposition', '').startswith('inline')
        ]
        return queryset.exclude(id__in=inlined_attachments)


class LogInline(admin.TabularInline):
    model = Log
    readonly_fields = fields = ['date', 'status', 'exception_type', 'message']
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


def requeue(modeladmin, request, queryset):
    """An admin action to requeue emails."""
    queryset.update(status=STATUS.queued)


requeue.short_description = 'Requeue selected emails'


class EmailContentInlineForm(forms.ModelForm):
    class Meta:
        model = PlaceholderContent
        fields = ['language', 'placeholder_name', 'content', 'base_file']
        widgets = {
            'base_file': HiddenInput(),  # Make base_file hidden
        }

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        if 'content' in self.initial:
            self.initial['content'] = render_placeholder_content(self.initial['content'])

    def save(self, commit=True):

        instance = super().save(commit=False)

        instance.content = convert_media_urls_to_tags(self.cleaned_data['content'])

        if commit:
            instance.save()

        return instance


class EmailContentInlineFormset(forms.BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class EmailContentInline(admin.TabularInline):
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
        formset = super(EmailContentInline, self).get_formset(request, obj, **kwargs)
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


class RecipientInline(admin.TabularInline):
    model = Recipient
    extra = 0

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class EmailAdmin(admin.ModelAdmin):
    list_display = [
        'truncated_message_id',
        #'to_display',
        'shortened_subject',
        'status',
        'last_updated',
        'scheduled_time',
        'use_template',
    ]
    search_fields = ['to', 'subject']
    readonly_fields = ['message_id', 'language', 'render_subject', 'render_plaintext_body', 'render_html_body']
    inlines = [RecipientInline, AttachmentInline, LogInline, ]
    list_filter = ['status', 'template__name']
    actions = [requeue]

    def get_urls(self):
        urls = [
            re_path(
                r'^(?P<pk>\d+)/image/(?P<content_id>[0-9a-f]{32})$',
                self.fetch_email_image,
                name='sendmail_email_image',
            ),
            re_path(r'^(?P<pk>\d+)/resend/$', self.resend, name='resend'),
        ]
        urls.extend(super().get_urls())
        return urls

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('template')

    def to_display(self, instance):
        return ', '.join([str(to) for to in instance.to])

    def truncated_message_id(self, instance):
        if instance.message_id:
            return Truncator(instance.message_id[1:-1]).chars(10)
        return str(instance.id)

    to_display.short_description = _('To')
    to_display.admin_order_field = 'to'
    truncated_message_id.short_description = 'Message-ID'

    def has_add_permission(self, request):
        return False

    def shortened_subject(self, instance):
        subject = instance.subject
        return Truncator(subject).chars(100)

    shortened_subject.short_description = _('Subject')
    shortened_subject.admin_order_field = 'subject'

    def use_template(self, instance):
        return bool(instance.template_id)

    use_template.short_description = _('Use Template')
    use_template.boolean = True

    def get_fieldsets(self, request, obj=None):
        fields = ['from_email', 'priority', ('status', 'scheduled_time')]
        if obj.message_id:
            fields.insert(0, 'message_id')
        fieldsets = [(None, {'fields': fields})]
        has_plaintext_content, has_html_content = False, False
        for part in obj.email_message().message().walk():
            if not isinstance(part, SafeMIMEText):
                continue
            content_type = part.get_content_type()
            if content_type == 'text/plain':
                has_plaintext_content = True
            elif content_type == 'text/html':
                has_html_content = True

        if has_html_content:
            fieldsets.append((_('HTML Email'), {'fields': ['render_subject', 'render_html_body']}))
            if has_plaintext_content:
                fieldsets.append((_('Text Email'), {'classes': ['collapse'], 'fields': ['render_plaintext_body']}))
        elif has_plaintext_content:
            fieldsets.append((_('Text Email'), {'fields': ['render_subject', 'render_plaintext_body']}))

        return fieldsets

    def render_subject(self, instance):
        message = instance.email_message()
        return message.subject

    render_subject.short_description = _('Subject')

    def render_plaintext_body(self, instance):
        for message in instance.email_message().message().walk():
            if isinstance(message, SafeMIMEText) and message.get_content_type() == 'text/plain':
                return format_html('<pre>{}</pre>', message.get_payload())

    render_plaintext_body.short_description = _('Mail Body')

    def render_html_body(self, instance):
        pattern = re.compile('cid:([0-9a-f]{32})')
        url = reverse('admin:sendmail_email_image', kwargs={'pk': instance.id, 'content_id': 32 * '0'})
        url = url.replace(32 * '0', r'\1')
        for message in instance.email_message().message().walk():
            if isinstance(message, SafeMIMEText) and message.get_content_type() == 'text/html':
                payload = message.get_payload(decode=True).decode('utf-8')
                return clean_html(payload)

    render_html_body.short_description = _('HTML Body')

    def fetch_email_image(self, request, pk, content_id):
        instance = self.get_object(request, pk)
        for message in instance.email_message().message().walk():
            if message.get_content_maintype() == 'image' and message.get('Content-Id')[1:33] == content_id:
                return HttpResponse(message.get_payload(decode=True), content_type=message.get_content_type())
        return HttpResponseNotFound()

    def resend(self, request, pk):
        instance = self.get_object(request, pk)
        instance.dispatch()
        messages.info(request, 'Email has been sent again')
        return HttpResponseRedirect(reverse('admin:sendmail_email_change', args=[instance.pk]))


class LogAdmin(admin.ModelAdmin):
    list_display = ('date', 'email', 'status', get_message_preview)


class SubjectField(TextInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.attrs.update({'style': 'width: 610px;'})


class EmailTemplateAdminFormSet(BaseInlineFormSet):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class EmailTemplateAdminForm(forms.ModelForm):
    change_form_template = 'admin/sendmail/emailtemplate/change_form.html'
    language = forms.ChoiceField(
        choices=settings.LANGUAGES,
        required=False,
        label=_('Language'),
        help_text=_('Render template in alternative language'),
    )
    base_file = forms.ChoiceField(
        choices=get_base_files(),  # Set choices to the result of get_email_templates
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


class EmailTemplateInline(admin.StackedInline):
    form = EmailMergeContentForm
    # formset = EmailTemplateAdminFormSet
    model = EmailMergeContentModel
    extra = 0
    fields = ('language', 'subject', 'content', 'extra_attachments')
    formfield_overrides = {models.CharField: {'widget': SubjectField}}

    filter_horizontal = ('extra_attachments',)

    def has_add_permission(self, request, obj):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class EmailTemplateAdmin(admin.ModelAdmin):
    form = EmailTemplateAdminForm
    list_display = ('name', 'created')
    search_fields = ('name', 'description', 'subject')
    fieldsets = [
        (None, {'fields': ('name', 'description', 'base_file', 'extra_recipients')}),
        # (_('Default Content'), {'fields': ('subject', 'content')}),
    ]
    inlines = (EmailTemplateInline, EmailContentInline)
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
    #
    #     if not obj.language:
    #         obj.language = get_default_language()
    #
    #     obj.save()
    #
    #     # if the name got changed, also change the translated templates to match again
    #     if 'name' in form.changed_data:
    #         obj.translated_templates.update(name=obj.name)


class AttachmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'file']
    filter_horizontal = ['emails']
    search_fields = ['name']
    autocomplete_fields = ['emails']


@admin.register(EmailAddress)
class EmailAddressAdmin(admin.ModelAdmin):
    search_fields = ('email', 'first_name', 'last_name')
    list_display = ('email', 'first_name', 'last_name', 'gender', 'is_blocked')


# @admin.register(PlaceholderContent)
# class EmailContentAdmin(admin.ModelAdmin):
#     pass


admin.site.register(EmailModel, EmailAdmin)
admin.site.register(Log, LogAdmin)
admin.site.register(EmailMergeModel, EmailTemplateAdmin)
admin.site.register(Attachment, AttachmentAdmin)
