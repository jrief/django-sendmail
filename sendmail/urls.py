from django.urls import path

from sendmail import views

app_name = "sendmail"

urlpatterns = [
    path("track/<int:pk>/<path:img>", views.track, name='track'),
    path("click/<int:pk>/", views.click, name='click')
]
