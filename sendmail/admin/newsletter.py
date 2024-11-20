from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import format_html

from sendmail.models import Newsletter

from django import forms
from django.utils.safestring import mark_safe
import json


class JSONTableWidget(forms.Widget):
    template_name = 'widgets/json_table.html'

    def render(self, name, value, attrs=None, renderer=None):
        # Parse the JSON value or set it to an empty dictionary
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                value = {}

        # Build table rows for existing data
        rows = ""
        if value is None:
            value = {}
        for key, val in value.items():
            rows += f"""
            <tr>
                <td><input type="text" name="{name}_key[]" value="{key}" class="form-control" /></td>
                <td><input type="text" name="{name}_value[]" value="{val}" class="form-control" /></td>
            </tr>
            """

        # Render the table
        table_html = f"""
        <table class="table">
            <thead>
                <tr>
                    <th>Key</th>
                    <th>Value</th>
                </tr>
            </thead>
            <tbody>
                {rows}
                <tr>
                    <td><input type="text" name="{name}_key[]" class="form-control" /></td>
                    <td><input type="text" name="{name}_value[]" class="form-control" /></td>
                </tr>
            </tbody>
        </table>
        <input type="hidden" name="{name}" value='{json.dumps(value)}' />
        """
        return mark_safe(table_html)

    def value_from_datadict(self, data, files, name):
        # Reconstruct JSON from key-value pairs
        keys = data.getlist(f"{name}_key[]")
        values = data.getlist(f"{name}_value[]")
        return json.dumps({k: v for k, v in zip(keys, values) if k})


class NewsletterForm(forms.ModelForm):
    class Meta:
        model = Newsletter
        fields = '__all__'
        widgets = {
            'context': JSONTableWidget(),  # Assign the custom widget
        }


@admin.register(Newsletter)
class NewsletterAdmin(admin.ModelAdmin):
    list_display = ('name', 'to_recipients', 'total_emails', 'sent_emails', 'failed_emails', 'requeued_emails')
    form = NewsletterForm

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context['send_newsletter_button'] = format_html(
            '''
            <input type="submit" value="Send Many" name="_send_many"/>
            '''
        )
        return super().change_view(request, str(object_id), form_url=form_url, extra_context=extra_context)

    def response_change(self, request, obj):
        if "_send_many" in request.POST:
            obj.create()
            # return redirect(
            #     reverse(
            #         'admin:%s_%s_change' % (self.model._meta.app_label, self.model._meta.model_name),
            #         args=[obj.pk]
            #     ))

        return super().response_change(request, obj)

