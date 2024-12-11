from pathlib import Path

from django.conf import settings
from django.contrib.messages.storage import default_storage
from django.contrib.staticfiles.finders import find
from django.core.files.images import ImageFile
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseBadRequest, FileResponse
from django.shortcuts import get_object_or_404
from sendmail.models.emailmodel import EmailModel
from django.core.files.storage import default_storage
from django.contrib.staticfiles.storage import staticfiles_storage
from django.utils import timezone


def track(request, img, pk):
    email = get_object_or_404(EmailModel, pk=pk)
    print(f'Email with id {email.id} was opened')

    if isinstance(img, ImageFile):
        fileobj = img.open('rb')
    else:
        if default_storage.exists(img):
            fileobj = default_storage.open(img)
        elif staticfiles_storage.exists(img):
            fileobj = staticfiles_storage.open(img)
        elif settings.DEBUG:
            path = find(img)
            fullpath = Path(path) if path else None
            if not fullpath:
                raise FileNotFoundError(f"No such file in static: {img}")
            if not fullpath.is_file():
                raise IsADirectoryError(f"File {img} is not a file")
            fileobj = fullpath.open('rb')

        else:
            raise FileNotFoundError(f"No such file in static: {img}")


    if not email.opened_at:
        email.opened_at = timezone.now()
        email.save()

    response = FileResponse(fileobj, content_type="image/png")
    response["Cache-Control"] = "no-store"

    return response


def click(request, pk):
    email = get_object_or_404(EmailModel, pk=pk)
    if not (target_uri := request.GET.get('target_uri')):
        return HttpResponseBadRequest("Missing 'target_uri' parameter")

    if not email.clicked_at:
        email.clicked_at = timezone.now()
        email.save()

    return HttpResponseRedirect(target_uri)
