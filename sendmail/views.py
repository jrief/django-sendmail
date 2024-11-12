from django.urls import reverse

from .models import EmailMergeModel
from .mail import send
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages


def send_email_view(request, object_id):
    obj = get_object_or_404(EmailMergeModel, pk=object_id)
    admin_user = request.user
    admin_email = admin_user.email

    if not admin_email:
        messages.error(request, "Current admin user does not have an email address set.")
        return redirect(
            reverse('admin:%s_%s_change' % (EmailMergeModel._meta.app_label, EmailMergeModel._meta.model_name),
                    args=[object_id]))

    try:
        send(recipients=admin_email, template=obj, priority='now')
        messages.success(request, "Email sent successfully to {admin_email}".format(admin_email=admin_email))

    except Exception as e:
        messages.error(request, f"An error has occurred: {e}")

    return redirect(
        reverse('admin:%s_%s_change' % (EmailMergeModel._meta.app_label, EmailMergeModel._meta.model_name), args=[object_id]))
