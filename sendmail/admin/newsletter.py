from django.contrib import admin

from sendmail.models import Newsletter

from django import forms
from django.utils.safestring import mark_safe
import json


class JSONTableWidget(forms.Widget):
    template_name = 'widgets/json_table.html'

    def render(self, name, value, attrs=None, renderer=None):
        # Parse the JSON value or set it to an empty dictionary
        value = value or {}
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                value = {}

        # Build table rows for existing data
        rows = ""
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
    form = NewsletterForm
