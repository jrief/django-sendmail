
from django.conf import settings
from django.contrib.messages.storage import default_storage
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.files.storage import default_storage
from django.core.validators import URLValidator
from django.http import FileResponse, HttpResponseBadRequest, HttpResponseNotFound, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils import timezone

from sendmail.models.emailmodel import EmailModel
from sendmail.signals import email_clicked, email_opened
from sendmail.utils import get_path_from_static


def track(request, img, pk):
    email = get_object_or_404(EmailModel, pk=pk)
    email_opened.send(sender=EmailModel, email=email)

    if settings.DEBUG:
        try:
            path = get_path_from_static(img)
            fileobj = path.open('rb')
        except (FileNotFoundError, IsADirectoryError):
            return HttpResponseNotFound('Image not found')
    elif staticfiles_storage.exists(img):
        fileobj = staticfiles_storage.open(img)
    elif default_storage.exists(img):
        fileobj = default_storage.open(img)
    else:
        return HttpResponseNotFound('Image not found')

    response = FileResponse(fileobj, content_type='image/png')
    response["Cache-Control"] = "no-store"

    if not email.opened_at:
        email.opened_at = timezone.now()
        email.save()


    return response


def click(request, pk):
    email = get_object_or_404(EmailModel, pk=pk)
    email_clicked.send(sender=EmailModel, email=email)
    if not (target_uri := request.GET.get('target_uri')):
        return HttpResponseBadRequest("Missing 'target_uri' parameter")

    try:
        URLValidator()(target_uri)
    except:
        return HttpResponseBadRequest("Invalid 'target_uri' parameter")

    if not email.clicked_at:
        email.clicked_at = timezone.now()
        email.save()

    return HttpResponseRedirect(target_uri)
