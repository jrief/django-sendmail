from django.http import HttpResponse, HttpResponseRedirect, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from sendmail.models.emailmodel import EmailModel
from django.utils import timezone
from django.db import transaction


def track(request, pk):
    email = get_object_or_404(EmailModel, pk=pk)
    print(f'Email with id {email.id} was opened')
    if not email.opened_at:
        email.opened_at = timezone.now()
        email.save()

    pixel = (b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4'
             b'\x89\x00\x00\x00\nIDATx\xdac\x00\x01\x00\x00\x05\x00\x01\x0d\n\x2d\xb4\x00\x00\x00\x00IEND\xaeB`\x82')

    return HttpResponse(pixel, content_type="image/png")


def click(request, pk):
    email = get_object_or_404(EmailModel, pk=pk)
    if not (target_uri := request.GET.get('target_uri')):
        return HttpResponseBadRequest("Missing 'target_uri' parameter")

    if not email.clicked_at:
        email.clicked_at = timezone.now()
        email.save()

    return HttpResponseRedirect(target_uri)
