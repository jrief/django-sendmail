from __future__ import absolute_import, unicode_literals

#from sendmail.settings import get_celery_enabled
# This will make sure the app is always imported when
# Django starts so that shared_task will use this app.

# if get_celery_enabled():
#     from .celery import app as celery_app
#     __all__ = ("celery_app",)
