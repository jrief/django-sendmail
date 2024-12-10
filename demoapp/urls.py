from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from demoapp import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('ckeditor/', include('ckeditor_uploader.urls')),
    path('sendmail/', include('sendmail.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
