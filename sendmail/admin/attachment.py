from django.contrib import admin

from sendmail.models.attachment import Attachment


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'file']
    filter_horizontal = ['emails']
    search_fields = ['name']
    autocomplete_fields = ['emails']


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
